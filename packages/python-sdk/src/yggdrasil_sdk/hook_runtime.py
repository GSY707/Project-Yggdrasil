from __future__ import annotations

from typing import Any

from .catalog import build_module_catalog_snapshot, load_in_process_plugin
from .hooks import HookNames


def active_module_ids() -> list[str]:
    snapshot = build_module_catalog_snapshot()
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    return [
        manifest.module_id
        for manifest in snapshot.manifests
        if installs_by_module_id[manifest.module_id].desired_state == "enabled"
        and installs_by_module_id[manifest.module_id].lifecycle_state in {"active", "degraded", "discovered"}
    ]


def load_active_module(module_id: str):
    snapshot = build_module_catalog_snapshot()
    manifests_by_module_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    manifest = manifests_by_module_id.get(module_id)
    install = installs_by_module_id.get(module_id)
    if manifest is None or install is None or not manifest.entry_point:
        raise KeyError(f"Module not available: {module_id}")
    if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded", "discovered"}:
        raise RuntimeError(f"Module {module_id} is not active.")
    return load_in_process_plugin(manifest.entry_point)


def _normalize_hook_result(result: Any) -> dict[str, Any]:
    if result is None:
        return {}
    if isinstance(result, dict):
        return dict(result)
    if isinstance(result, (list, tuple)):
        return {"items": [item for item in result]}
    return {"value": result}


def call_module_hook(module_id: str, hook_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        plugin = load_active_module(module_id)
    except Exception:
        return None
    registrations = sorted(
        [registration for registration in plugin.register_hooks() if registration.name == hook_name],
        key=lambda registration: registration.order,
    )
    for registration in registrations:
        return _normalize_hook_result(registration.handler(payload))
    return None


def collect_hook_results(
    hook_name: str,
    payload: dict[str, Any],
    *,
    module_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    snapshot = build_module_catalog_snapshot()
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    selected_ids = set(module_ids) if module_ids is not None else None
    collected: list[dict[str, Any]] = []

    for manifest in snapshot.manifests:
        if selected_ids is not None and manifest.module_id not in selected_ids:
            continue
        install = installs_by_module_id.get(manifest.module_id)
        if install is None:
            continue
        if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded", "discovered"}:
            continue
        if hook_name not in manifest.hooks or not manifest.entry_point:
            continue
        try:
            plugin = load_in_process_plugin(manifest.entry_point)
        except Exception:
            continue

        registrations = sorted(
            [registration for registration in plugin.register_hooks() if registration.name == hook_name],
            key=lambda registration: registration.order,
        )
        for registration in registrations:
            try:
                result = registration.handler(payload)
            except Exception as exc:
                collected.append(
                    {
                        "moduleId": manifest.module_id,
                        "hookName": hook_name,
                        "order": registration.order,
                        "error": str(exc),
                        "result": None,
                    }
                )
                continue
            collected.append(
                {
                    "moduleId": manifest.module_id,
                    "hookName": hook_name,
                    "order": registration.order,
                    "result": _normalize_hook_result(result),
                }
            )

    collected.sort(key=lambda item: (int(item.get("order") or 100), str(item.get("moduleId") or "")))
    return collected


def validate_memory_write(
    payload: dict[str, Any],
    *,
    module_ids: list[str] | None = None,
) -> dict[str, Any]:
    target_space_id = str(payload.get("targetSpaceId") or payload.get("spaceId") or "")
    target_branch_id = str(payload.get("targetBranchId") or payload.get("branchId") or "")
    merged = {
        "allowed": True,
        "status": "ok",
        "targetSpaceId": target_space_id,
        "targetBranchId": target_branch_id,
        "annotations": [],
        "blockers": [],
        "summaries": [],
        "appliedModules": [],
        "results": [],
    }

    for item in collect_hook_results(HookNames.MEMORY_WRITE_VALIDATE, payload, module_ids=module_ids):
        merged["results"].append(item)
        module_id = str(item.get("moduleId") or "unknown")
        if item.get("error"):
            merged["allowed"] = False
            merged["status"] = "error"
            merged["blockers"].append(f"{module_id}:{item['error']}")
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        merged["appliedModules"].append(module_id)
        if result.get("summary"):
            merged["summaries"].append(str(result["summary"]))
        if isinstance(result.get("annotations"), list):
            merged["annotations"].extend(annotation for annotation in result["annotations"] if isinstance(annotation, dict))
        if result.get("targetSpaceId") is not None:
            merged["targetSpaceId"] = str(result["targetSpaceId"])
        if result.get("targetBranchId") is not None:
            merged["targetBranchId"] = str(result["targetBranchId"])
        if isinstance(result.get("blockers"), list):
            merged["blockers"].extend(str(blocker) for blocker in result["blockers"])
        status = str(result.get("status") or "ok")
        if result.get("allowed") is False or status in {"deny", "error"}:
            merged["allowed"] = False
            merged["status"] = "error"

    if merged["blockers"]:
        merged["allowed"] = False
        merged["status"] = "error"
    return merged