from __future__ import annotations
from dataclasses import dataclass
import json
import os
import re
import ssl
import time
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from yggdrasil_sdk.support import new_id, normalize_excerpt
_DEEPSEEK_DEPRECATED_MODEL_NAMES = {"deepseek-chat", "deepseek-reasoner"}
_DEEPSEEK_REASONING_EFFORT_ALIASES = {
    "low": "high",
    "medium": "high",
    "high": "high",
    "xhigh": "max",
    "max": "max",
}
_LONGCAT_TOOL_CALL_PATTERN = re.compile(r"<longcat_tool_call>(?P<body>.*?)</longcat_tool_call>", re.IGNORECASE | re.DOTALL)
_LONGCAT_ARG_KEY_PATTERN = re.compile(r"<longcat_arg_key>(?P<value>.*?)</longcat_arg_key>", re.IGNORECASE | re.DOTALL)
_LONGCAT_ARG_VALUE_PATTERN = re.compile(r"<longcat_arg_value>(?P<value>.*?)</longcat_arg_value>", re.IGNORECASE | re.DOTALL)
_BLOCK_TOOL_CALLS_PATTERN = re.compile(r"<tool_calls>(?P<body>.*?)</tool_calls>", re.IGNORECASE | re.DOTALL)
_BLOCK_TOOL_TAG_PATTERN = re.compile(r"<(?P<name>[A-Za-z0-9_.-]+)>(?P<body>.*?)</(?P=name)>", re.DOTALL)
_BLOCK_TOOL_ARG_PATTERN = re.compile(r"<(?P<name>[A-Za-z0-9_.-]+)>(?P<value>.*?)</(?P=name)>", re.DOTALL)
_INLINE_TOOL_TAG_PATTERN = re.compile(r"<(?P<name>[A-Za-z0-9_.-]+)(?P<attrs>\s+[^<>]*?)?\s*/>", re.DOTALL)
_INLINE_TOOL_ATTR_PATTERN = re.compile(r'(?P<name>[A-Za-z0-9_.-]+)\s*=\s*"(?P<value>[^"]*)"')
_LONGCAT_ARGUMENT_ALIASES = {
    "file_path": "path",
    "start_line": "startLine",
    "end_line": "endLine",
    "old_text": "oldText",
    "new_text": "newText",
    "working_directory": "workingDirectory",
    "timeout_ms": "timeoutMs",
}
@dataclass
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
        "default_model": "LongCat-2.0",
        "models": {
            "LongCat-2.0": {
                "quality": 0.82,
                "cost_per_1k_input": 0.0,
                "cost_per_1k_output": 0.0,
                "latency_ms": 760,
                "context_window": 1_000_000,
                "max_output_tokens": 128000,
                "priority": 101,
            },
        },
        "quality": 0.82,
        "cost_per_1k_input": 0.0,
        "cost_per_1k_output": 0.0,
        "latency_ms": 760,
        "context_window": 1_000_000,
        "max_output_tokens": 128000,
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
                "max_output_tokens": 384000,
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
                "max_output_tokens": 384000,
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
    if normalized.lower() in _DEEPSEEK_DEPRECATED_MODEL_NAMES:
        raise ValueError(
            f"DeepSeek model name {normalized!r} is deprecated; use 'deepseek-v4-flash' or 'deepseek-v4-pro'."
        )
    return normalized
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
            "max_output_tokens": int(profile.get("max_output_tokens") or 0),
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
        "max_output_tokens": int(model_profile.get("max_output_tokens") or 0),
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
    from yggdrasil_sdk.provider_config import provider_key

    candidates = {
        "longcat": provider_key("longcat"),
        "openrouter": provider_key("openrouter"),
        "deepseek_direct": provider_key("deepseek_direct"),
        "vectorengine": provider_key("vectorengine"),
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
                    "maxOutputTokens": int(model_profile.get("max_output_tokens") or 0),
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
def _usage_value(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current
def _usage_int(payload: dict[str, Any], *candidates: tuple[str, ...]) -> int:
    saw_zero = False
    for candidate in candidates:
        value = _usage_value(payload, *candidate)
        if value is None:
            continue
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
        if parsed == 0:
            saw_zero = True
    if saw_zero:
        return 0
    return 0
def _normalize_usage(raw_usage: dict[str, Any], messages: list[dict[str, Any]], output_text: str) -> dict[str, int]:
    input_tokens = _usage_int(
        raw_usage,
        ("prompt_tokens",),
        ("input_tokens",),
    )
    if input_tokens <= 0:
        input_tokens = sum(_estimate_tokens(str(item.get("content") or "")) for item in messages)

    output_tokens = _usage_int(
        raw_usage,
        ("completion_tokens",),
        ("output_tokens",),
    )
    if output_tokens <= 0:
        output_tokens = _estimate_tokens(output_text)

    cache_hit_input_tokens = _usage_int(
        raw_usage,
        ("cache_read_tokens",),
        ("cache_read_input_tokens",),
        ("input_cached_tokens",),
        ("cached_input_tokens",),
        ("prompt_tokens_details", "cached_tokens"),
        ("input_tokens_details", "cached_tokens"),
        ("effectiveCachedTokens",),
        ("cached_tokens",),
    )
    cache_write_input_tokens = _usage_int(
        raw_usage,
        ("cache_write_tokens",),
        ("cache_creation_input_tokens",),
        ("cache_write_input_tokens",),
        ("prompt_tokens_details", "cache_creation_tokens"),
        ("input_tokens_details", "cache_creation_tokens"),
    )
    reasoning_tokens = _usage_int(
        raw_usage,
        ("reasoning_tokens",),
        ("completion_tokens_details", "reasoning_tokens"),
        ("output_tokens_details", "reasoning_tokens"),
    )
    total_tokens = _usage_int(raw_usage, ("total_tokens",))
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return {
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": total_tokens,
        "cacheHitInputTokens": max(cache_hit_input_tokens, 0),
        "cacheWriteInputTokens": max(cache_write_input_tokens, 0),
        "nonCacheInputTokens": max(input_tokens - cache_hit_input_tokens, 0),
        "reasoningTokens": max(reasoning_tokens, 0),
    }
def _extract_text_content(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        parts: list[str] = []
        for item in payload:
            fragment = _extract_text_content(item)
            if fragment:
                parts.append(fragment)
        return "\n".join(parts)

    if isinstance(payload, dict):
        for key in ("text", "output_text"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value

        payload_type = str(payload.get("type") or "").strip().lower()
        if payload_type in {"text", "output_text", "input_text"}:
            for key in ("text", "output_text", "content"):
                value = payload.get(key)
                fragment = _extract_text_content(value)
                if fragment:
                    return fragment

        for key in ("content", "output", "message", "delta"):
            value = payload.get(key)
            fragment = _extract_text_content(value)
            if fragment:
                return fragment

    return ""
def _coerce_tool_argument_value(value: str) -> Any:
    candidate = str(value or "").strip()
    if not candidate:
        return ""
    try:
        return json.loads(candidate)
    except Exception:
        return candidate
def _strip_json_code_fence(text: str) -> str:
    stripped = str(text or "").strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()
def _extract_json_object_candidate(text: str) -> str:
    stripped = _strip_json_code_fence(text)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped
def _parse_tool_arguments_text(arguments_text: str) -> dict[str, Any]:
    candidate = _extract_json_object_candidate(arguments_text)
    if not candidate:
        return {}

    for attempt in (
        candidate,
        re.sub(r",\s*([}\]])", r"\1", candidate),
        candidate.replace("'", '"'),
    ):
        try:
            parsed = json.loads(attempt)
            if isinstance(parsed, dict):
                return parsed
            return {"value": parsed}
        except Exception:
            pass

    # Fallback for loose `key=value` / `key: value` payloads frequently emitted in non-strict tool mode.
    kv_pairs = re.findall(r"([A-Za-z_][A-Za-z0-9_.-]*)\s*(?:=|:)\s*([^,\n]+)", candidate)
    if kv_pairs:
        repaired: dict[str, Any] = {}
        for raw_key, raw_value in kv_pairs:
            normalized_key = _LONGCAT_ARGUMENT_ALIASES.get(raw_key.strip(), raw_key.strip())
            repaired[normalized_key] = _coerce_tool_argument_value(raw_value.strip().strip('"').strip("'"))
        if repaired:
            return repaired

    return {"_raw": str(arguments_text or "").strip()}
def _extract_longcat_tagged_tool_calls(content: str) -> tuple[str, list[dict[str, Any]]]:
    if not content or "<longcat_tool_call>" not in content.lower():
        return str(content or ""), []

    tool_calls: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        body = str(match.group("body") or "")
        tool_name = body.split("<longcat_arg_key>", 1)[0].strip()
        keys = [str(item).strip() for item in _LONGCAT_ARG_KEY_PATTERN.findall(body)]
        values = [str(item).strip() for item in _LONGCAT_ARG_VALUE_PATTERN.findall(body)]
        arguments: dict[str, Any] = {}
        for key, value in zip(keys, values):
            normalized_key = _LONGCAT_ARGUMENT_ALIASES.get(key, key)
            arguments[normalized_key] = _coerce_tool_argument_value(value)
        if tool_name:
            tool_calls.append(
                {
                    "id": new_id("toolcall", tool_name),
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return ""

    cleaned = _LONGCAT_TOOL_CALL_PATTERN.sub(_replace, content)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, tool_calls
def _extract_inline_tool_tags(content: str) -> tuple[str, list[dict[str, Any]]]:
    if not content or "<" not in content or "/>" not in content:
        return str(content or ""), []

    tool_calls: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        name = str(match.group("name") or "").strip()
        if "." not in name:
            return str(match.group(0) or "")
        attributes_text = str(match.group("attrs") or "")
        arguments = {
            _LONGCAT_ARGUMENT_ALIASES.get(attr_name, attr_name): _coerce_tool_argument_value(attr_value)
            for attr_name, attr_value in _INLINE_TOOL_ATTR_PATTERN.findall(attributes_text)
        }
        tool_calls.append(
            {
                "id": new_id("toolcall", name),
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                },
            }
        )
        return ""

    cleaned = _INLINE_TOOL_TAG_PATTERN.sub(_replace, content)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, tool_calls
def _extract_block_tool_tags(content: str) -> tuple[str, list[dict[str, Any]]]:
    if not content or "<tool_calls>" not in content.lower():
        return str(content or ""), []

    tool_calls: list[dict[str, Any]] = []

    def _replace_container(match: re.Match[str]) -> str:
        body = str(match.group("body") or "")
        for tool_match in _BLOCK_TOOL_TAG_PATTERN.finditer(body):
            name = str(tool_match.group("name") or "").strip()
            if "." not in name:
                continue
            tool_body = str(tool_match.group("body") or "")
            arguments = {
                _LONGCAT_ARGUMENT_ALIASES.get(arg_name, arg_name): _coerce_tool_argument_value(arg_value)
                for arg_name, arg_value in _BLOCK_TOOL_ARG_PATTERN.findall(tool_body)
                if "." not in str(arg_name)
            }
            tool_calls.append(
                {
                    "id": new_id("toolcall", name),
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": json.dumps(arguments, ensure_ascii=False),
                    },
                }
            )
        return ""

    cleaned = _BLOCK_TOOL_CALLS_PATTERN.sub(_replace_container, content)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, tool_calls
def _extract_embedded_tool_calls(content: str) -> tuple[str, list[dict[str, Any]]]:
    cleaned_text, tool_calls = _extract_longcat_tagged_tool_calls(content)
    cleaned_text, block_tool_calls = _extract_block_tool_tags(cleaned_text)
    cleaned_text, inline_tool_calls = _extract_inline_tool_tags(cleaned_text)
    return cleaned_text, [*tool_calls, *block_tool_calls, *inline_tool_calls]
def _extract_tool_call_candidates(payload: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if isinstance(payload, list):
        for item in payload:
            candidates.extend(_extract_tool_call_candidates(item))
        return candidates

    if not isinstance(payload, dict):
        return candidates

    raw_tool_calls = payload.get("tool_calls") if isinstance(payload.get("tool_calls"), list) else None
    if raw_tool_calls:
        candidates.extend([call for call in raw_tool_calls if isinstance(call, dict)])

    payload_type = str(payload.get("type") or "").strip().lower()
    if payload_type in {"function_call", "tool_call", "tool_use"}:
        function_payload = payload.get("function") if isinstance(payload.get("function"), dict) else None
        name = str(
            payload.get("name")
            or (function_payload or {}).get("name")
            or payload.get("tool_name")
            or payload.get("function_name")
            or ""
        ).strip()
        arguments_payload = payload.get("arguments")
        if arguments_payload is None:
            arguments_payload = payload.get("input")
        if arguments_payload is None and function_payload is not None:
            arguments_payload = function_payload.get("arguments")
        candidates.append(
            {
                "id": payload.get("id") or payload.get("call_id"),
                "index": payload.get("index"),
                "type": payload.get("type") or "function",
                "function": {
                    "name": name,
                    "arguments": arguments_payload if arguments_payload is not None else "{}",
                },
            }
        )

    for key in ("content", "output", "message", "delta"):
        value = payload.get(key)
        if value is not None:
            candidates.extend(_extract_tool_call_candidates(value))
    return candidates
def _normalize_tool_call(raw_call: dict[str, Any], *, default_name: str) -> dict[str, Any] | None:
    function_payload = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
    name = str(function_payload.get("name") or default_name or "").strip()
    arguments_payload = function_payload.get("arguments")
    if arguments_payload is None:
        arguments_payload = raw_call.get("arguments")
    if arguments_payload is None:
        arguments_payload = raw_call.get("input")
    if not name and arguments_payload is None and raw_call.get("id") is None and raw_call.get("call_id") is None and raw_call.get("index") is None:
        return None
    return {
        "id": raw_call.get("id") or raw_call.get("call_id"),
        "index": raw_call.get("index"),
        "type": str(raw_call.get("type") or "function"),
        "function": {
            "name": name,
            "arguments": arguments_payload if arguments_payload is not None else "",
        },
    }
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
    elif raw_call.get("call_id"):
        entry["id"] = str(raw_call["call_id"])
    if raw_call.get("type"):
        entry["type"] = str(raw_call["type"])
    function_payload = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
    entry_function = entry["function"]
    name_part = str(
        function_payload.get("name")
        or raw_call.get("name")
        or raw_call.get("tool_name")
        or raw_call.get("function_name")
        or ""
    )
    if name_part:
        entry_function["name"] += name_part
    arguments_part = function_payload.get("arguments")
    if arguments_part is None:
        arguments_part = raw_call.get("arguments")
    if arguments_part is None:
        arguments_part = raw_call.get("input")
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
    stream_chunk_count = 0

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
            stream_chunk_count += 1
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
            raw_tool_calls = _extract_tool_call_candidates(payload)
            if first_token_latency_ms is None and (content_fragment or reasoning_fragment or raw_tool_calls):
                first_token_latency_ms = round((time.perf_counter() - request_started_at) * 1000.0, 2)
            if content_fragment:
                content_parts.append(content_fragment)
            if reasoning_fragment:
                reasoning_parts.append(reasoning_fragment)
            for raw_call in raw_tool_calls:
                if isinstance(raw_call, dict):
                    normalized_call = _normalize_tool_call(raw_call, default_name="")
                    if normalized_call is not None:
                        _merge_stream_tool_call(tool_calls, normalized_call)
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
            "streamTelemetry": {
                "chunkCount": stream_chunk_count,
                "idleTimeoutSeconds": timeout_seconds,
                "durationMs": round((time.perf_counter() - request_started_at) * 1000.0, 2),
            },
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
    output_text = (
        _extract_text_content(message.get("content"))
        or _extract_text_content(message.get("output_text"))
        or _extract_text_content(choice.get("output_text"))
        or _extract_text_content(raw_response.get("output_text"))
        or _extract_text_content(raw_response.get("output"))
        or _extract_text_content(choice.get("delta"))
    )
    output_text, embedded_tool_calls = _extract_embedded_tool_calls(output_text)
    reasoning_content = (
        _extract_text_content(message.get("reasoning_content"))
        or _extract_text_content(choice.get("reasoning_content"))
        or _extract_text_content(raw_response.get("reasoning_content"))
    )
    tool_calls: list[dict[str, Any]] = []
    raw_tool_calls = _extract_tool_call_candidates(message)
    if not raw_tool_calls:
        raw_tool_calls = _extract_tool_call_candidates(choice)
    if not raw_tool_calls:
        raw_tool_calls = _extract_tool_call_candidates(raw_response)
    if not raw_tool_calls and embedded_tool_calls:
        raw_tool_calls = embedded_tool_calls
    for raw_call in raw_tool_calls:
        if not isinstance(raw_call, dict):
            continue
        function_payload = raw_call.get("function") if isinstance(raw_call.get("function"), dict) else {}
        name = str(function_payload.get("name") or "").strip()
        original_name = tool_name_aliases.get(name, name)
        arguments_text = str(function_payload.get("arguments") or "{}").strip() or "{}"
        arguments = _parse_tool_arguments_text(arguments_text)
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
    normalized_usage = _normalize_usage(usage if isinstance(usage, dict) else {}, messages, output_text)
    input_tokens = normalized_usage["inputTokens"]
    output_tokens = normalized_usage["outputTokens"]
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
        "usage": normalized_usage,
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
def _effective_max_tokens(max_tokens: int | None, model_profile: dict[str, Any]) -> int | None:
    profile_max = int(model_profile.get("max_output_tokens") or 0)
    if profile_max > 0:
        return profile_max
    if max_tokens is None:
        return None
    return max(1, int(max_tokens))
def _is_retryable_transport_error(exc: Exception) -> bool:
    if isinstance(exc, (TimeoutError, ConnectionResetError, ConnectionAbortedError, BrokenPipeError, ssl.SSLError)):
        return True
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
    provider_idle_timeout_seconds = max(
        int(os.environ.get("YGGDRASIL_LLM_STREAM_IDLE_TIMEOUT_SECONDS") or timeout_seconds),
        1,
    )

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
        normalized_reasoning_effort = _normalize_reasoning_effort(
            reasoning_effort or os.environ.get("YGGDRASIL_LLM_DEEPSEEK_REASONING_EFFORT") or "max"
        )
        if thinking_type != "disabled" and normalized_reasoning_effort is not None:
            request_payload["reasoning_effort"] = normalized_reasoning_effort
    if temperature is not None:
        request_payload["temperature"] = temperature
    effective_max_tokens = _effective_max_tokens(max_tokens, model_profile)
    if effective_max_tokens is not None:
        request_payload["max_tokens"] = effective_max_tokens
        if max_tokens is not None and int(max_tokens) != effective_max_tokens:
            request_payload["yggdrasil_requested_max_tokens"] = int(max_tokens)
    prepared_tools, tool_name_aliases = _prepare_provider_tools(config.provider, tools)
    if prepared_tools:
        request_payload["tools"] = prepared_tools
        request_payload["tool_choice"] = "auto"

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
    _transport_retries: list[dict[str, Any]] = []

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
            _raw_response, first_token_latency_ms = _assemble_stream_response(
                http_request,
                timeout_seconds=provider_idle_timeout_seconds,
            )
            if _transport_retries:
                _raw_response.setdefault("streamReconnect", {"attempts": len(_transport_retries)})
                _raw_response["streamReconnect"]["events"] = list(_transport_retries)
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
            retry_event = {
                "attempt": _attempt,
                "stream": bool(attempt_payload.get("stream")),
                "errorType": type(exc).__name__,
                "error": normalize_excerpt(str(exc), 240),
                "idleTimeoutSeconds": provider_idle_timeout_seconds,
            }
            if _attempt < _max_retries and _is_retryable_transport_error(exc):
                _transport_retries.append(retry_event)
                time.sleep(min(_backoff_base ** _attempt, 60.0))
                continue
            if _attempt < _max_retries:
                _transport_retries.append(retry_event)
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
