from __future__ import annotations

from pathlib import Path
from typing import Any

from .app_catalog import active_application_id, load_effective_application_config
from .hook_runtime import active_module_ids


CORE_RUNTIME_CAPABILITIES = [
    "pause-resume",
    "task-takeover",
]


def _normalize_capability_values(values: Any) -> list[str]:
    if values is None:
        return []
    normalized: list[str] = []
    for item in values if isinstance(values, list) else [values]:
        capability = str(item).strip()
        if capability:
            normalized.append(capability)
    return normalized


def resolve_runtime_application_id(app_id: str | None = None, workspace_root: Path | None = None) -> str:
    return str(app_id or active_application_id(workspace_root))


def resolve_application_active_capabilities(
    app_id: str | None = None,
    requested_capabilities: list[str] | None = None,
    workspace_root: Path | None = None,
) -> list[str]:
    available_capabilities = active_module_ids()
    available_lookup = set(available_capabilities)

    if requested_capabilities is not None:
        preferred = _normalize_capability_values(requested_capabilities)
    else:
        try:
            effective_config = load_effective_application_config(
                resolve_runtime_application_id(app_id, workspace_root),
                workspace_root,
            )
        except KeyError:
            preferred = list(available_capabilities)
        else:
            preferred = _normalize_capability_values(effective_config.get("defaultCapabilities"))

    for capability in CORE_RUNTIME_CAPABILITIES:
        if capability not in preferred:
            preferred.append(capability)

    resolved: list[str] = []
    seen: set[str] = set()
    for capability in preferred:
        if capability not in available_lookup or capability in seen:
            continue
        seen.add(capability)
        resolved.append(capability)

    if resolved or requested_capabilities is not None:
        return resolved
    return list(available_capabilities)