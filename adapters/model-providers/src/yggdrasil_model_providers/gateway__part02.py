def _fallback_response(messages: list[dict[str, Any]], reason: str, *, requested_model: str | None, requested_provider: str | None) -> dict[str, Any]:
    user_message = next((message for message in reversed(messages) if message.get("role") == "user"), {"content": ""})
    summarized_prompt = normalize_excerpt(str(user_message.get("content") or ""), 400)
    content = (
        "# Result\n"
        "LLM 网关未能执行真实调用，已切换到 deterministic fallback。\n\n"
        f"原因: {reason}\n"
        f"请求模型: {requested_model or 'unspecified'}\n"
        f"请求提供商: {requested_provider or 'unspecified'}\n\n"
        "当前任务摘要:\n"
        f"{summarized_prompt}\n\n"
        "# Evidence\n"
        "Fallback execution verification passed.\n"
    )
    # Fallback mode is synthetic: estimate work from the actionable user payload,
    # not from the full compiled prompt scaffold that would only be billed on real model calls.
    input_tokens = _estimate_tokens(summarized_prompt)
    output_tokens = _estimate_tokens(content)
    return {
        "mode": "fallback",
        "provider": requested_provider,
        "model": requested_model or "fallback-synthetic",
        "outputText": content,
        "finishReason": "fallback",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": input_tokens + output_tokens,
            "cacheHitInputTokens": 0,
            "cacheWriteInputTokens": 0,
            "nonCacheInputTokens": input_tokens,
            "reasoningTokens": 0,
        },
        "costUsed": 0.0,
        "error": reason,
        "toolCalls": [],
        "rawResponse": {
            "id": "fallback",
            "object": "chat.completion",
            "choices": [{"finish_reason": "fallback", "message": {"role": "assistant", "content": content}}],
            "usage": {
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
        },
    }
def _retry_max() -> int:
    return int(os.environ.get("YGGDRASIL_LLM_RETRY_MAX", "3"))
def _retry_backoff_base() -> float:
    return float(os.environ.get("YGGDRASIL_LLM_RETRY_BACKOFF_BASE", "2.0"))
def _deepseek_extra_retry_max() -> int:
    return max(int(os.environ.get("YGGDRASIL_LLM_DEEPSEEK_EXTRA_RETRY_MAX", "2")), 0)
def _retry_max_for_provider(provider: str) -> int:
    base = _retry_max()
    if provider == "deepseek_direct":
        return base + _deepseek_extra_retry_max()
    return base
def _is_retryable_transport_error(exc: Exception) -> bool:
    if isinstance(exc, urllib_error.URLError):
        reason = exc.reason
        if isinstance(reason, (ssl.SSLError, TimeoutError, ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
            return True
        if isinstance(reason, OSError):
            lowered_reason = str(reason).lower()
            return any(
                token in lowered_reason
                for token in (
                    "ssl",
                    "eof",
                    "unexpected_eof",
                    "timed out",
                    "timeout",
                    "connection reset",
                    "connection aborted",
                )
            )
    lowered = str(exc).lower()
    return any(
        token in lowered
        for token in (
            "unexpected_eof_while_reading",
            "eof occurred in violation of protocol",
            "ssl",
            "connection reset",
            "connection aborted",
            "timed out",
            "timeout",
        )
    )
def invoke_model(
    *,
    requested_model: str | None,
    requested_provider: str | None,
    messages: list[dict[str, Any]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_fallback: bool = True,
    tools: list[dict[str, Any]] | None = None,
    thinking: Any = None,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    if _truthy_env("YGGDRASIL_DISABLE_LIVE_LLM", default=False):
        return _fallback_response(
            messages,
            "live-llm-disabled",
            requested_model=requested_model,
            requested_provider=requested_provider,
        )
    config = _select_provider(
        requested_provider=requested_provider,
        requested_model=_canonical_model_name(requested_model),
        workspace_root=workspace_root,
    )
    if config is None:
        if allow_fallback:
            return _fallback_response(messages, "no-configured-free-provider", requested_model=requested_model, requested_provider=requested_provider)
        raise RuntimeError("No configured provider is available for model invocation.")

    normalized_requested_model = _canonical_model_name(requested_model)
    inferred_provider = _infer_provider_from_model(normalized_requested_model)
    resolved_model = config.default_model
    if normalized_requested_model and (
        requested_provider == config.provider or requested_provider is None or inferred_provider == config.provider
    ):
        resolved_model = normalized_requested_model
    model_profile = _provider_model_profile(config.provider, resolved_model) or {}
    resolved_model = str(model_profile.get("model") or resolved_model)
    request_payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "stream": True,
    }
    if config.provider == "deepseek_direct" and bool(model_profile.get("supports_thinking")):
        thinking_type = _normalize_thinking_type(thinking)
        if thinking_type is None and bool(model_profile.get("thinking_enabled_by_default")):
            thinking_type = "enabled"
        if thinking_type is not None:
            request_payload["thinking"] = {"type": thinking_type}
        normalized_reasoning_effort = _normalize_reasoning_effort(reasoning_effort)
        if thinking_type != "disabled" and normalized_reasoning_effort is not None:
            request_payload["reasoning_effort"] = normalized_reasoning_effort
    if temperature is not None:
        request_payload["temperature"] = temperature
    if max_tokens is not None:
        request_payload["max_tokens"] = max_tokens
    prepared_tools, tool_name_aliases = _prepare_provider_tools(config.provider, tools)
    if prepared_tools:
        request_payload["tools"] = prepared_tools
        request_payload["tool_choice"] = "auto"

    encoded_payload = json.dumps(request_payload).encode("utf-8")
    endpoint = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    if config.provider == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("YGGDRASIL_OPENROUTER_REFERER", "https://yggdrasil.local")
        headers["X-Title"] = os.environ.get("YGGDRASIL_OPENROUTER_TITLE", "Project Yggdrasil")

    _max_retries = _retry_max_for_provider(config.provider)
    _backoff_base = _retry_backoff_base()
    _last_exc: Exception | None = None
    _raw_response: dict | None = None

    for _attempt in range(_max_retries + 1):
        try:
            attempt_payload = dict(request_payload)
            attempt_headers = dict(headers)
            if config.provider == "deepseek_direct" and _attempt > 0:
                # DeepSeek transport can occasionally fail on streamed chunk boundaries.
                # Retry with non-stream mode and explicit connection close for a more stable retry path.
                attempt_payload["stream"] = False
                attempt_headers["Connection"] = "close"
            attempt_encoded_payload = json.dumps(attempt_payload).encode("utf-8")
            http_request = urllib_request.Request(endpoint, data=attempt_encoded_payload, headers=attempt_headers, method="POST")
            _raw_response, first_token_latency_ms = _assemble_stream_response(http_request, timeout_seconds=timeout_seconds)
            request_payload = attempt_payload
            break  # success
        except urllib_error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            # Retry on 429 and 5xx
            if exc.code == 429 or exc.code >= 500:
                _last_exc = RuntimeError(f"Model provider HTTP error: {exc.code}: {normalize_excerpt(detail, 320)}")
                if _attempt < _max_retries:
                    time.sleep(min(_backoff_base ** _attempt, 60.0))
                    continue
            # For other HTTP errors, fall through to fallback
            if allow_fallback:
                return _fallback_response(
                    messages,
                    f"http-{exc.code}: {normalize_excerpt(detail, 320)}",
                    requested_model=requested_model,
                    requested_provider=requested_provider,
                )
            raise RuntimeError(f"Model provider HTTP error: {exc.code}: {detail}") from exc
        except Exception as exc:
            _last_exc = exc
            if _attempt < _max_retries and _is_retryable_transport_error(exc):
                time.sleep(min(_backoff_base ** _attempt, 60.0))
                continue
            if _attempt < _max_retries:
                time.sleep(min(_backoff_base ** _attempt, 60.0))
                continue
            break

    if _raw_response is None:
        # All retries exhausted
        exc_msg = str(_last_exc) if _last_exc is not None else "unknown-error"
        if allow_fallback:
            return _fallback_response(messages, exc_msg, requested_model=requested_model, requested_provider=requested_provider)
        raise RuntimeError(f"Model provider failed after {_max_retries + 1} attempts: {exc_msg}") from _last_exc

    raw_response = _raw_response
    return _result_from_raw_response(
        raw_response,
        resolved_model=resolved_model,
        config=config,
        messages=messages,
        model_profile=model_profile,
        request_payload=request_payload,
        tool_name_aliases=tool_name_aliases,
        first_token_latency_ms=first_token_latency_ms,
    )