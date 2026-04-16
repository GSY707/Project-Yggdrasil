from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from yggdrasil_sdk.support import normalize_excerpt, resolve_workspace_root


_QUOTES_TRANSLATION = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


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
        "default_model": "deepseek-chat",
        "quality": 0.82,
        "cost_per_1k_input": 0.14,
        "cost_per_1k_output": 0.28,
        "latency_ms": 1100,
        "context_window": 64000,
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


def _normalize_text(value: str) -> str:
    return value.translate(_QUOTES_TRANSLATION)


def _truthy_env(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _llm_txt_api_keys(workspace_root: Path | None = None) -> dict[str, str]:
    root = resolve_workspace_root(workspace_root)
    path = root / "LLM.txt"
    if not path.exists():
        return {}

    keys: dict[str, str] = {}
    in_api_keys = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = _normalize_text(raw_line.rstrip())
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("api_keys"):
            in_api_keys = True
            continue
        if in_api_keys and not raw_line.startswith((" ", "\t")):
            break
        if not in_api_keys:
            continue
        match = re.match(r"^\s*([A-Za-z0-9_]+)\s*[:：]\s*\"?([^\"\n]+)\"?\s*$", line)
        if match is None:
            continue
        provider, token = match.groups()
        token = token.strip().strip("\"'")
        if token:
            keys[provider] = token
    return keys


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
    default_model = os.environ.get(f"YGGDRASIL_LLM_MODEL_{provider.upper()}", profile["default_model"])
    return ProviderConfig(
        provider=provider,
        api_key=api_key,
        base_url=str(base_url).rstrip("/"),
        default_model=str(default_model),
        quality=float(profile["quality"]),
        cost_per_1k_input=float(profile["cost_per_1k_input"]),
        cost_per_1k_output=float(profile["cost_per_1k_output"]),
        latency_ms=int(profile["latency_ms"]),
        context_window=int(profile["context_window"]),
        free_tier=bool(profile["free_tier"]),
        priority=int(profile["priority"]),
    )


def _available_provider_configs(workspace_root: Path | None = None) -> dict[str, ProviderConfig]:
    tokens = _llm_txt_api_keys(workspace_root)
    tokens.update(_environment_provider_keys())
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
        candidates.append(
            {
                "model": config.default_model,
                "provider": config.provider,
                "quality": config.quality,
                "costPer1k": round(config.cost_per_1k_input + config.cost_per_1k_output, 3),
                "latencyMs": config.latency_ms,
                "contextWindow": config.context_window,
                "freeTier": config.free_tier,
            }
        )
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


def _fallback_response(messages: list[dict[str, str]], reason: str, *, requested_model: str | None, requested_provider: str | None) -> dict[str, Any]:
    user_message = next((message for message in reversed(messages) if message.get("role") == "user"), {"content": ""})
    content = (
        "LLM 网关未能执行真实调用，已切换到 deterministic fallback。\n\n"
        f"原因: {reason}\n"
        f"请求模型: {requested_model or 'unspecified'}\n"
        f"请求提供商: {requested_provider or 'unspecified'}\n\n"
        "当前任务摘要:\n"
        f"{normalize_excerpt(str(user_message.get('content') or ''), 800)}"
    )
    input_tokens = sum(_estimate_tokens(str(message.get("content") or "")) for message in messages)
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


def invoke_model(
    *,
    requested_model: str | None,
    requested_provider: str | None,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
    workspace_root: Path | None = None,
    timeout_seconds: int = 90,
    allow_fallback: bool = True,
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
        requested_model=requested_model,
        workspace_root=workspace_root,
    )
    if config is None:
        if allow_fallback:
            return _fallback_response(messages, "no-configured-free-provider", requested_model=requested_model, requested_provider=requested_provider)
        raise RuntimeError("No configured provider is available for model invocation.")

    resolved_model = requested_model if requested_provider == config.provider and requested_model else config.default_model
    request_payload: dict[str, Any] = {
        "model": resolved_model,
        "messages": messages,
        "stream": False,
    }
    if temperature is not None:
        request_payload["temperature"] = temperature
    if max_tokens is not None:
        request_payload["max_tokens"] = max_tokens

    encoded_payload = json.dumps(request_payload).encode("utf-8")
    endpoint = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    if config.provider == "openrouter":
        headers["HTTP-Referer"] = os.environ.get("YGGDRASIL_OPENROUTER_REFERER", "https://yggdrasil.local")
        headers["X-Title"] = os.environ.get("YGGDRASIL_OPENROUTER_TITLE", "Project Yggdrasil")

    try:
        http_request = urllib_request.Request(endpoint, data=encoded_payload, headers=headers, method="POST")
        with urllib_request.urlopen(http_request, timeout=timeout_seconds) as response:
            raw_response = json.loads(response.read().decode("utf-8"))
    except urllib_error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if allow_fallback:
            return _fallback_response(
                messages,
                f"http-{exc.code}: {normalize_excerpt(detail, 320)}",
                requested_model=requested_model,
                requested_provider=requested_provider,
            )
        raise RuntimeError(f"Model provider HTTP error: {exc.code}: {detail}") from exc
    except Exception as exc:
        if allow_fallback:
            return _fallback_response(messages, str(exc), requested_model=requested_model, requested_provider=requested_provider)
        raise

    choice = ((raw_response.get("choices") or [{}])[0]) if isinstance(raw_response, dict) else {}
    message = choice.get("message") or {}
    output_text = _extract_text_content(message.get("content"))
    usage = raw_response.get("usage") if isinstance(raw_response, dict) else {}
    input_tokens = int(usage.get("prompt_tokens") or usage.get("input_tokens") or sum(_estimate_tokens(str(item.get("content") or "")) for item in messages))
    output_tokens = int(usage.get("completion_tokens") or usage.get("output_tokens") or _estimate_tokens(output_text))
    total_tokens = int(usage.get("total_tokens") or input_tokens + output_tokens)
    cost_used = round((input_tokens * config.cost_per_1k_input + output_tokens * config.cost_per_1k_output) / 1000.0, 6)
    return {
        "mode": "live",
        "provider": config.provider,
        "model": resolved_model,
        "outputText": output_text,
        "finishReason": choice.get("finish_reason") or "stop",
        "usage": {
            "inputTokens": input_tokens,
            "outputTokens": output_tokens,
            "totalTokens": total_tokens,
        },
        "costUsed": cost_used,
        "error": None,
        "rawResponse": raw_response,
        "requestPayload": request_payload,
    }