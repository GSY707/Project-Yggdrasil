from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from yggdrasil_sdk.support import new_id, normalize_excerpt


_DEEPSEEK_MODEL_ALIASES = {
    "deepseek-chat": "deepseek-v4-flash",
    "deepseek-reasoner": "deepseek-v4-pro",
}
_DEEPSEEK_REASONING_EFFORT_ALIASES = {
    "low": "high",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    api_key: str
    base_url: str
    default_model: str
    quality: float
    cost_per_1k_input: float
    cost_per_1k_output: float
    latency_ms: int
    context_window: int
    free_tier: bool
    priority: int


PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "longcat": {
        "base_url": "https://api.longcat.chat/openai/v1",
        "default_model": "LongCat-Flash-Lite",
        "quality": 0.78,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "latency_ms": 700,
        "context_window": 128000,
        "free_tier": True,
        "priority": 100,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-oss-20b:free",
        "quality": 0.84,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "latency_ms": 1200,
        "context_window": 128000,
        "free_tier": True,
        "priority": 90,
    },
    "deepseek_direct": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-v4-flash",
        "models": {
            "deepseek-v4-flash": {
                "quality": 0.84,
                "cost_per_1k_input": 0.001,
                "cost_per_1k_output": 0.002,
                "latency_ms": 850,
                "context_window": 1_000_000,
                "supports_thinking": True,
                "thinking_enabled_by_default": True,
                "priority": 35,
            },
            "deepseek-v4-pro": {
                "quality": 0.91,
                "cost_per_1k_input": 0.003,
                "cost_per_1k_output": 0.006,
                "latency_ms": 1350,
                "context_window": 1_000_000,
                "supports_thinking": True,
                "thinking_enabled_by_default": True,
                "priority": 34,
            },
        },
        "free_tier": False,
        "priority": 30,
    },
    "vectorengine": {
        "base_url": os.environ.get("YGGDRASIL_LLM_BASE_URL_VECTORENGINE", "https://api.vectorengine.ai/v1"),
        "default_model": os.environ.get("YGGDRASIL_LLM_MODEL_VECTORENGINE", "gpt-4o-mini"),
        "quality": 0.8,
        "cost_per_1k_input": 0.2,
        "cost_per_1k_output": 0.2,
        "latency_ms": 1000,
        "context_window": 128000,
        "free_tier": False,
        "priority": 20,
    },
}


def _truthy_env(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _canonical_model_name(model: str | None) -> str | None:
    if model is None:
        return None
    normalized = str(model).strip()
    if not normalized:
        return None
    return _DEEPSEEK_MODEL_ALIASES.get(normalized.lower(), normalized)


def _provider_model_profile(provider: str, model: str | None) -> dict[str, Any] | None:
    profile = PROVIDER_PROFILES.get(provider)
    if profile is None:
        return None

    resolved_model = _canonical_model_name(model) or str(profile.get("default_model") or "")
    model_profiles = profile.get("models")
    if not isinstance(model_profiles, dict):
        return {
            "model": resolved_model,
            "quality": float(profile["quality"]),
            "cost_per_1k_input": float(profile["cost_per_1k_input"]),
            "cost_per_1k_output": float(profile["cost_per_1k_output"]),
            "latency_ms": int(profile["latency_ms"]),
            "context_window": int(profile["context_window"]),
            "priority": int(profile["priority"]),
            "supports_thinking": False,
            "thinking_enabled_by_default": False,
        }

    if resolved_model not in model_profiles:
        resolved_model = str(profile.get("default_model") or next(iter(model_profiles)))
    model_profile = model_profiles.get(resolved_model)
    if not isinstance(model_profile, dict):
        return None
    return {
        "model": resolved_model,
        "quality": float(model_profile["quality"]),
        "cost_per_1k_input": float(model_profile["cost_per_1k_input"]),
        "cost_per_1k_output": float(model_profile["cost_per_1k_output"]),
        "latency_ms": int(model_profile["latency_ms"]),
        "context_window": int(model_profile["context_window"]),
        "priority": int(model_profile.get("priority", profile["priority"])),
        "supports_thinking": bool(model_profile.get("supports_thinking", False)),
        "thinking_enabled_by_default": bool(model_profile.get("thinking_enabled_by_default", False)),
    }


def _provider_catalog_entries(provider: str, default_model: str | None) -> list[dict[str, Any]]:
    profile = PROVIDER_PROFILES.get(provider)
    if profile is None:
        return []

    model_profiles = profile.get("models")
    if not isinstance(model_profiles, dict):
        model_profile = _provider_model_profile(provider, default_model)
        return [model_profile] if model_profile is not None else []

    configured_default = (_provider_model_profile(provider, default_model) or {}).get("model")
    entries: list[dict[str, Any]] = []
    for model_name in model_profiles:
        model_profile = _provider_model_profile(provider, model_name)
        if model_profile is None:
            continue
        if model_profile["model"] == configured_default:
            model_profile["priority"] = int(model_profile["priority"]) + 1
        entries.append(model_profile)
    entries.sort(key=lambda item: int(item["priority"]), reverse=True)
    return entries


def _normalize_thinking_type(value: Any) -> str | None:
    candidate = value
    if isinstance(candidate, dict):
        candidate = candidate.get("type")
    if isinstance(candidate, bool):
        return "enabled" if candidate else "disabled"
    if candidate is None:
        return None
    lowered = str(candidate).strip().lower()
    if lowered in {"1", "true", "enabled", "enable", "on", "thinking"}:
        return "enabled"
    if lowered in {"0", "false", "disabled", "disable", "off", "none"}:
        return "disabled"
    return None


def _normalize_reasoning_effort(value: Any) -> str | None:
    if value is None:
        return None
    return _DEEPSEEK_REASONING_EFFORT_ALIASES.get(str(value).strip().lower())


def _prepare_provider_tools(provider: str, tools: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]] | None, dict[str, str]]:
    if not tools:
        return None, {}
    if provider != "deepseek_direct":
        return [dict(tool) for tool in tools], {}

    prepared: list[dict[str, Any]] = []
    aliases: dict[str, str] = {}
    for index, tool in enumerate(tools, start=1):
        payload = dict(tool)
        function_payload = dict(payload.get("function") or {})
        original_name = str(function_payload.get("name") or "").strip()
        aliased_name = original_name
        if original_name and re.fullmatch(r"^[A-Za-z0-9_-]+$", original_name) is None:
            sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", original_name).strip("_") or "tool"
            aliased_name = f"deepseek_tool_{index}_{sanitized}"
        function_payload["name"] = aliased_name
        payload["function"] = function_payload
        prepared.append(payload)
        if original_name:
            aliases[aliased_name] = original_name
    return prepared, aliases


def _environment_provider_keys() -> dict[str, str]:
    candidates = {
        "longcat": os.environ.get("YGGDRASIL_LLM_API_KEY_LONGCAT") or os.environ.get("LONGCAT_API_KEY"),
        "openrouter": os.environ.get("YGGDRASIL_LLM_API_KEY_OPENROUTER") or os.environ.get("OPENROUTER_API_KEY"),
        "deepseek_direct": os.environ.get("YGGDRASIL_LLM_API_KEY_DEEPSEEK") or os.environ.get("DEEPSEEK_API_KEY"),
        "vectorengine": os.environ.get("YGGDRASIL_LLM_API_KEY_VECTORENGINE") or os.environ.get("VECTORENGINE_API_KEY"),
    }
    if os.environ.get("YGGDRASIL_LLM_PROVIDER") and os.environ.get("YGGDRASIL_LLM_API_KEY"):
        candidates[str(os.environ["YGGDRASIL_LLM_PROVIDER"]).strip()] = str(os.environ["YGGDRASIL_LLM_API_KEY"]).strip()
    return {provider: token for provider, token in candidates.items() if token}


def _build_provider_config(provider: str, api_key: str) -> ProviderConfig | None:
    profile = PROVIDER_PROFILES.get(provider)
    if profile is None:
        return None
    base_url = os.environ.get(f"YGGDRASIL_LLM_BASE_URL_{provider.upper()}", profile["base_url"])
    configured_model = os.environ.get(f"YGGDRASIL_LLM_MODEL_{provider.upper()}", profile["default_model"])
    model_profile = _provider_model_profile(provider, configured_model)
    if model_profile is None:
        return None
    return ProviderConfig(
        provider=provider,
        api_key=api_key,
        base_url=str(base_url).rstrip("/"),
        default_model=str(model_profile["model"]),
        quality=float(model_profile["quality"]),
        cost_per_1k_input=float(model_profile["cost_per_1k_input"]),
        cost_per_1k_output=float(model_profile["cost_per_1k_output"]),
        latency_ms=int(model_profile["latency_ms"]),
        context_window=int(model_profile["context_window"]),
        free_tier=bool(profile["free_tier"]),
        priority=int(profile["priority"]),
    )


def _available_provider_configs(workspace_root: Path | None = None) -> dict[str, ProviderConfig]:
    tokens = _environment_provider_keys()
    configs: dict[str, ProviderConfig] = {}
    for provider, token in tokens.items():
        config = _build_provider_config(provider, token)
        if config is not None:
            configs[provider] = config
    return configs


def get_provider_catalog(workspace_root: Path | None = None) -> list[dict[str, Any]]:
    if _truthy_env("YGGDRASIL_DISABLE_LIVE_LLM", default=False):
        return []
    allow_paid = _truthy_env("YGGDRASIL_ALLOW_PAID_MODELS", default=False)
    configs = _available_provider_configs(workspace_root)
    candidates: list[dict[str, Any]] = []
    for config in sorted(configs.values(), key=lambda item: item.priority, reverse=True):
        if not config.free_tier and not allow_paid:
            continue
        for model_profile in _provider_catalog_entries(config.provider, config.default_model):
            candidates.append(
                {
                    "model": str(model_profile["model"]),
                    "provider": config.provider,
                    "quality": float(model_profile["quality"]),
                    "costPer1k": round(float(model_profile["cost_per_1k_input"]) + float(model_profile["cost_per_1k_output"]), 3),
                    "latencyMs": int(model_profile["latency_ms"]),
                    "contextWindow": int(model_profile["context_window"]),
                    "freeTier": config.free_tier,
                    "_priority": int(model_profile["priority"]),
                }
            )
    candidates.sort(key=lambda item: (int(item.get("_priority", 0)), float(item.get("quality", 0.0))), reverse=True)
    for candidate in candidates:
        candidate.pop("_priority", None)
    return candidates


def _infer_provider_from_model(model: str | None) -> str | None:
    if not model:
        return None
    lowered = model.lower()
    if lowered.startswith("longcat"):
        return "longcat"
    if lowered.startswith("deepseek"):
        return "deepseek_direct"
    if "/" in lowered or lowered.endswith(":free"):
        return "openrouter"
    return None


def _select_provider(
    *,
    requested_provider: str | None,
    requested_model: str | None,
    workspace_root: Path | None = None,
) -> ProviderConfig | None:
    allow_paid = _truthy_env("YGGDRASIL_ALLOW_PAID_MODELS", default=False)
    configs = _available_provider_configs(workspace_root)
    if requested_provider and requested_provider in configs:
        config = configs[requested_provider]
        if config.free_tier or allow_paid:
            return config
    inferred_provider = _infer_provider_from_model(requested_model)
    if inferred_provider and inferred_provider in configs:
        config = configs[inferred_provider]
        if config.free_tier or allow_paid:
            return config
    eligible = [config for config in configs.values() if config.free_tier or allow_paid]
    if not eligible:
        return None
    eligible.sort(key=lambda item: item.priority, reverse=True)
    return eligible[0]


def _estimate_tokens(text: str) -> int:
    compact = " ".join(text.split())
    return max(1, len(compact) // 4)


def _extract_text_content(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts: list[str] = []
        for item in payload:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict) and item.get("type") == "text" and item.get("text"):
                parts.append(str(item["text"]))
        return "\n".join(parts)
    if isinstance(payload, dict) and payload.get("text"):
        return str(payload["text"])
    return str(payload or "")


def _merge_stream_tool_call(tool_calls: dict[int, dict[str, Any]], raw_call: dict[str, Any]) -> None:
    raw_index = raw_call.get("index")
    try:
        index = int(raw_index)
    except (TypeError, ValueError):
        index = len(tool_calls)
    entry = tool_calls.setdefault(
        index,
        {
            "id": None,
            "type": "function",
            "function": {"name": "", "arguments": ""},
        },
    )
    if raw_call.get("id"):
        entry["id"] = str(raw_call["id"])
    if raw_call.get("type"):
        entry["type"] = str(raw_call["type"])
    function_payload = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
    entry_function = entry["function"]
    name_part = str(function_payload.get("name") or "")
    if name_part:
        entry_function["name"] += name_part
    arguments_part = function_payload.get("arguments")
    if arguments_part is not None:
        entry_function["arguments"] += str(arguments_part)


def _assemble_stream_response(http_request, *, timeout_seconds: int) -> tuple[dict[str, Any], float | None]:
    request_started_at = time.perf_counter()
    first_token_latency_ms: float | None = None
    response_id: str | None = None
    response_model: str | None = None
    finish_reason: str | None = None
    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    usage: dict[str, Any] | None = None
    tool_calls: dict[int, dict[str, Any]] = {}

    with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
        while True:
            raw_line = response.readline()
            if not raw_line:
                break
            stripped = raw_line.strip()
            if not stripped:
                continue
            if not stripped.startswith(b"data:"):
                body = raw_line + response.read()
                return json.loads(body.decode("utf-8")), None

            event_payload = stripped[len(b"data:") :].strip()
            if not event_payload:
                continue
            if event_payload == b"[DONE]":
                break

            chunk = json.loads(event_payload.decode("utf-8"))
            if response_id is None and chunk.get("id"):
                response_id = str(chunk["id"])
            if response_model is None and chunk.get("model"):
                response_model = str(chunk["model"])
            if isinstance(chunk.get("usage"), dict):
                usage = dict(chunk["usage"])

            choice = ((chunk.get("choices") or [{}])[0]) if isinstance(chunk, dict) else {}
            delta = choice.get("delta") if isinstance(choice.get("delta"), dict) else {}
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            payload = delta or message

            content_fragment = _extract_text_content(payload.get("content"))
            reasoning_fragment = (
                _extract_text_content(payload.get("reasoning_content"))
                if payload.get("reasoning_content") is not None
                else ""
            )
            raw_tool_calls = payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else []
            if first_token_latency_ms is None and (content_fragment or reasoning_fragment or raw_tool_calls):
                first_token_latency_ms = round((time.perf_counter() - request_started_at) * 1000.0, 2)
            if content_fragment:
                content_parts.append(content_fragment)
            if reasoning_fragment:
                reasoning_parts.append(reasoning_fragment)
            for raw_call in raw_tool_calls:
                if isinstance(raw_call, dict):
                    _merge_stream_tool_call(tool_calls, raw_call)
            if choice.get("finish_reason") is not None:
                finish_reason = str(choice.get("finish_reason") or "stop")

    serialized_tool_calls = [tool_calls[index] for index in sorted(tool_calls)]
    message_payload: dict[str, Any] = {
        "role": "assistant",
        "content": "".join(content_parts),
    }
    if reasoning_parts:
        message_payload["reasoning_content"] = "".join(reasoning_parts)
    if serialized_tool_calls:
        message_payload["tool_calls"] = serialized_tool_calls

    return (
        {
            "id": response_id or new_id("stream", "chat-completion"),
            "object": "chat.completion",
            "model": response_model,
            "choices": [
                {
                    "finish_reason": finish_reason or "stop",
                    "message": message_payload,
                }
            ],
            "usage": usage or {},
            "stream": True,
        },
        first_token_latency_ms,
    )


def _result_from_raw_response(
    raw_response: dict[str, Any],
    *,
    resolved_model: str,
    config: ProviderConfig,
    messages: list[dict[str, Any]],
    model_profile: dict[str, Any],
    request_payload: dict[str, Any],
    tool_name_aliases: dict[str, str],
    first_token_latency_ms: float | None,
) -> dict[str, Any]:
    choice = ((raw_response.get("choices") or [{}])[0]) if isinstance(raw_response, dict) else {}
    message = choice.get("message") or {}
    output_text = _extract_text_content(message.get("content"))
    reasoning_content = _extract_text_content(message.get("reasoning_content")) if message.get("reasoning_content") is not None else ""
    tool_calls: list[dict[str, Any]] = []
    for raw_call in message.get("tool_calls") or []:
        if not isinstance(raw_call, dict):
            continue
        function_payload = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
        name = str(function_payload.get("name") or "").strip()
        original_name = tool_name_aliases.get(name, name)
        arguments_text = str(function_payload.get("arguments") or "{}").strip() or "{}"
        try:
            arguments = json.loads(arguments_text)
            if not isinstance(arguments, dict):
                arguments = {"value": arguments}
        except Exception:
            arguments = {"_raw": arguments_text}
        tool_calls.append(
            {
                "id": str(raw_call.get("id") or new_id("toolcall", original_name or resolved_model)),
                "type": str(raw_call.get("type") or "function"),
                "name": original_name,
                "arguments": arguments,
                "argumentsText": arguments_text,
            }
        )
    usage = raw_response.get("usage") if isinstance(raw_response, dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or sum(_estimate_tokens(str(item.get("content") or "")) for item in messages))
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or _estimate_tokens(output_text))
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    cost_per_1k_input = float(model_profile.get("cost_per_1k_input", config.cost_per_1k_input))
    cost_per_1k_output = float(model_profile.get("cost_per_1k_output", config.cost_per_1k_output))
    cost_used = round((input_tokens * cost_per_1k_input + output_tokens * cost_per_1k_output) / 1000.0, 6)
    return {
        "mode": "live",
        "provider": config.provider,
        "model": resolved_model,
        "outputText": output_text,
        "reasoningContent": reasoning_content or None,
        "finishReason": choice.get("finish_reason") or "stop",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": total_tokens,
        },
        "costUsed": cost_used,
        "error": None,
        "toolCalls": tool_calls,
        "rawResponse": raw_response,
        "requestPayload": request_payload,
        "firstTokenLatencyMs": first_token_latency_ms,
    }


def _fallback_response(messages: list[dict[str, Any]], reason: str, *, requested_model: str | None, requested_provider: str | None) -> dict[str, Any]:
    user_message = next((message for message in reversed(messages) if message.get("role") == "user"), {"content": ""})
    summarized_prompt = normalize_excerpt(str(user_message.get("content") or ""), 400)
    content = (
        "LLM 网关未能执行真实调用，已切换到 deterministic fallback。\n\n"
        f"原因: {reason}\n"
        f"请求模型: {requested_model or 'unspecified'}\n"
        f"请求提供商: {requested_provider or 'unspecified'}\n\n"
        "当前任务摘要:\n"
        f"{summarized_prompt}"
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

    _max_retries = _retry_max()
    _backoff_base = _retry_backoff_base()
    _last_exc: Exception | None = None
    _raw_response: dict | None = None

    for _attempt in range(_max_retries + 1):
        try:
            http_request = urllib_request.Request(endpoint, data=encoded_payload, headers=headers, method="POST")
            _raw_response, first_token_latency_ms = _assemble_stream_response(http_request, timeout_seconds=timeout_seconds)
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