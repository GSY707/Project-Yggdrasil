from __future__ import annotations

import os
from typing import Any


PROVIDER_ENV_GROUPS: tuple[dict[str, object], ...] = (
    {
        "id": "longcat",
        "label": "LongCat",
        "envNames": ("YGGDRASIL_LLM_API_KEY_LONGCAT", "LONGCAT_API_KEY"),
    },
    {
        "id": "openrouter",
        "label": "OpenRouter",
        "envNames": ("YGGDRASIL_LLM_API_KEY_OPENROUTER", "OPENROUTER_API_KEY"),
    },
    {
        "id": "deepseek_direct",
        "label": "DeepSeek",
        "envNames": ("YGGDRASIL_LLM_API_KEY_DEEPSEEK", "DEEPSEEK_API_KEY"),
    },
    {
        "id": "vectorengine",
        "label": "VectorEngine",
        "envNames": ("YGGDRASIL_LLM_API_KEY_VECTORENGINE", "VECTORENGINE_API_KEY"),
    },
    {
        "id": "generic",
        "label": "Generic LLM gateway",
        "envNames": ("YGGDRASIL_LLM_API_KEY",),
    },
)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def live_llm_disabled() -> bool:
    return _truthy(os.environ.get("YGGDRASIL_DISABLE_LIVE_LLM"))


def configured_provider_keys() -> list[dict[str, object]]:
    configured: list[dict[str, object]] = []
    for provider in PROVIDER_ENV_GROUPS:
        env_names = tuple(str(name) for name in provider["envNames"])
        configured_env_names = [
            env_name
            for env_name in env_names
            if str(os.environ.get(env_name) or "").strip()
        ]
        if configured_env_names:
            configured.append(
                {
                    "id": str(provider["id"]),
                    "label": str(provider["label"]),
                    "envNames": list(env_names),
                    "configuredEnvNames": configured_env_names,
                }
            )
    return configured


def has_provider_key() -> bool:
    return bool(configured_provider_keys())


def provider_configuration_status() -> dict[str, Any]:
    configured = configured_provider_keys()
    required_any_of = sorted(
        {
            env_name
            for provider in PROVIDER_ENV_GROUPS
            for env_name in tuple(str(name) for name in provider["envNames"])
        }
    )
    if live_llm_disabled():
        return {
            "status": "warning",
            "mode": "live-disabled",
            "configuredProviders": configured,
            "requiredAnyOf": required_any_of,
            "disabledEnv": "YGGDRASIL_DISABLE_LIVE_LLM",
            "detail": "Live LLM is disabled; tasks may use deterministic fallback.",
            "remediation": "Remove YGGDRASIL_DISABLE_LIVE_LLM or configure a provider key before real user tasks.",
        }
    if configured:
        return {
            "status": "ready",
            "mode": "configured",
            "configuredProviders": configured,
            "requiredAnyOf": required_any_of,
            "disabledEnv": "YGGDRASIL_DISABLE_LIVE_LLM",
            "detail": "At least one model provider key is configured.",
            "remediation": None,
        }
    return {
        "status": "blocked",
        "mode": "missing-provider-key",
        "configuredProviders": [],
        "requiredAnyOf": required_any_of,
        "disabledEnv": "YGGDRASIL_DISABLE_LIVE_LLM",
        "detail": "No model provider key is configured.",
        "remediation": "Create infra/product.env or .env with at least one provider key, then restart services.",
    }


__all__ = [
    "PROVIDER_ENV_GROUPS",
    "configured_provider_keys",
    "has_provider_key",
    "live_llm_disabled",
    "provider_configuration_status",
]
