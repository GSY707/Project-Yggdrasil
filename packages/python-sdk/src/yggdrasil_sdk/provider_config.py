from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .support import ensure_state_dir, read_json, write_json


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

PROVIDER_SECRETS_FILE = "provider-secrets.json"


def _secrets_path(workspace_root: Path | None = None) -> Path:
    return ensure_state_dir(workspace_root) / PROVIDER_SECRETS_FILE


def _stored_provider_keys(workspace_root: Path | None = None) -> dict[str, str]:
    payload = read_json(_secrets_path(workspace_root), {})
    keys = payload.get("keys") if isinstance(payload, dict) else None
    if not isinstance(keys, dict):
        return {}
    return {str(key): str(value).strip() for key, value in keys.items() if str(value).strip()}


def provider_key(provider_id: str, workspace_root: Path | None = None) -> str | None:
    provider = next((item for item in PROVIDER_ENV_GROUPS if item["id"] == provider_id), None)
    if provider is None:
        return None
    for env_name in tuple(str(name) for name in provider["envNames"]):
        value = str(os.environ.get(env_name) or "").strip()
        if value:
            return value
    return _stored_provider_keys(workspace_root).get(provider_id)


def save_provider_key(provider_id: str, api_key: str, workspace_root: Path | None = None) -> dict[str, Any]:
    if not any(item["id"] == provider_id for item in PROVIDER_ENV_GROUPS):
        raise KeyError(provider_id)
    normalized = api_key.strip()
    if len(normalized) < 8:
        raise ValueError("API key must contain at least 8 characters.")
    path = _secrets_path(workspace_root)
    keys = _stored_provider_keys(workspace_root)
    keys[provider_id] = normalized
    write_json(path, {"version": 1, "keys": keys})
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return provider_configuration_status(workspace_root)


def delete_provider_key(provider_id: str, workspace_root: Path | None = None) -> dict[str, Any]:
    if not any(item["id"] == provider_id for item in PROVIDER_ENV_GROUPS):
        raise KeyError(provider_id)
    path = _secrets_path(workspace_root)
    keys = _stored_provider_keys(workspace_root)
    keys.pop(provider_id, None)
    write_json(path, {"version": 1, "keys": keys})
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return provider_configuration_status(workspace_root)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def live_llm_disabled() -> bool:
    return _truthy(os.environ.get("YGGDRASIL_DISABLE_LIVE_LLM"))


def configured_provider_keys(workspace_root: Path | None = None) -> list[dict[str, object]]:
    configured: list[dict[str, object]] = []
    for provider in PROVIDER_ENV_GROUPS:
        env_names = tuple(str(name) for name in provider["envNames"])
        configured_env_names = [
            env_name
            for env_name in env_names
            if str(os.environ.get(env_name) or "").strip()
        ]
        stored_key = _stored_provider_keys(workspace_root).get(str(provider["id"]))
        if configured_env_names or stored_key:
            configured.append(
                {
                    "id": str(provider["id"]),
                    "label": str(provider["label"]),
                    "envNames": list(env_names),
                    "configuredEnvNames": configured_env_names,
                    "source": "environment" if configured_env_names else "web-settings",
                    "keyHint": f"••••{stored_key[-4:]}" if stored_key else None,
                }
            )
    return configured


def has_provider_key() -> bool:
    return bool(configured_provider_keys())


def provider_configuration_status(workspace_root: Path | None = None) -> dict[str, Any]:
    configured = configured_provider_keys(workspace_root)
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
    "provider_key",
    "save_provider_key",
    "delete_provider_key",
]
