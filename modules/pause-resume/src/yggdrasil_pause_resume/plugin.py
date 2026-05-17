from __future__ import annotations

from pathlib import Path
from typing import Any

from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.module import BaseModulePlugin, HookRegistration
from yggdrasil_sdk.runtime_kernel import load_package_entry
from yggdrasil_sdk.runtime_kernel.takeover import restore_takeover_work_tree_pointer
from yggdrasil_sdk.support import new_id, normalize_excerpt


def _summarize_pending_actions(pending_actions: list[dict[str, Any]]) -> str:
    if not pending_actions:
        return "No pending external actions were recorded at safe-stop."
    labels = [str(action.get("kind") or action.get("type") or "action") for action in pending_actions[:4] if isinstance(action, dict)]
    return "Pending actions: " + ", ".join(labels)


def _restored_request_state(snapshot_pending_actions: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for action in snapshot_pending_actions:
        if not isinstance(action, dict):
            continue
        request_state = action.get("requestState") if isinstance(action.get("requestState"), dict) else None
        if request_state is None:
            continue
        merged.update(request_state)
    if isinstance(merged.get("takeoverProtocol"), dict):
        merged["takeoverProtocol"] = restore_takeover_work_tree_pointer(dict(merged["takeoverProtocol"]))
    return merged


class PauseResumeModule(BaseModulePlugin):
    module_id = "pause-resume"

    def manifest_path(self) -> Path:
        return Path(__file__).resolve().parents[2] / "yggdrasil.module.yaml"

    def register_hooks(self) -> tuple[HookRegistration, ...]:
        return (
            HookRegistration(name=HookNames.MODULE_ENABLE_PREFLIGHT, handler=self.enable_preflight),
            HookRegistration(name=HookNames.MODULE_HEALTH_REPORT, handler=self.report_health),
            HookRegistration(name=HookNames.TASK_PAUSE_PREPARE, handler=self.prepare_pause, side_effects="controlled-write"),
            HookRegistration(name=HookNames.TASK_RESUME_REHYDRATE, handler=self.rehydrate_resume),
        )

    def enable_preflight(self, payload: dict[str, object]) -> dict[str, object]:
        install = payload.get("install") if isinstance(payload.get("install"), dict) else {}
        if str(install.get("runtimeMode") or "") != "in-process":
            return {"status": "error", "summary": "Pause Resume requires in-process runtime mode."}
        return {"status": "ok", "summary": "Pause Resume preflight passed."}

    def report_health(self, payload: dict[str, object]) -> dict[str, object]:
        return {
            "status": "healthy",
            "summary": "Pause Resume is ready to prepare snapshots and rehydrate task state.",
        }

    def prepare_pause(self, payload: dict[str, object]) -> dict[str, object]:
        pending_writes = payload.get("pendingWrites") if isinstance(payload.get("pendingWrites"), list) else []
        pending_actions = payload.get("pendingActions") if isinstance(payload.get("pendingActions"), list) else []
        active_tool_calls = payload.get("activeToolCalls") if isinstance(payload.get("activeToolCalls"), list) else []
        current_context_state = payload.get("currentContextState") if isinstance(payload.get("currentContextState"), list) else []
        current_response_state = str(payload.get("currentResponseState") or "completed")
        blockers: list[str] = []
        if current_response_state not in {"completed", "idle", "drained"}:
            blockers.append("response-not-finished")
        if active_tool_calls:
            blockers.append("active-tool-calls")
        safe_to_pause = not blockers
        task_id = str(payload.get("taskId") or new_id("task", self.module_id, stable=True))
        resume_message = (
            f"Resume task {task_id} with {len(current_context_state)} retained context items, "
            f"{len(pending_writes)} flushed writes, and {len(pending_actions)} pending actions."
        )
        return {
            "safeToPause": safe_to_pause,
            "blockers": blockers,
            "snapshotDelta": {
                "resumeMessage": normalize_excerpt(resume_message, 180),
                "safeStopReason": "protocol-safe-stop",
                "pendingActions": [
                    {
                        "kind": "resume-digest",
                        "summary": _summarize_pending_actions([action for action in pending_actions if isinstance(action, dict)]),
                    }
                ],
            },
            "summary": (
                f"Prepared safe-stop for task {task_id}: {len(pending_writes)} writes flushed, "
                f"{len(current_context_state)} context items retained."
            ),
        }

    def rehydrate_resume(self, payload: dict[str, object]) -> dict[str, object]:
        task_snapshot = payload.get("taskSnapshot") if isinstance(payload.get("taskSnapshot"), dict) else {}
        root_mounts = payload.get("rootMounts") if isinstance(payload.get("rootMounts"), dict) else {}
        context_ref = task_snapshot.get("contextRef") if isinstance(task_snapshot.get("contextRef"), dict) else None
        root_mount_ref = task_snapshot.get("rootMountRef") if isinstance(task_snapshot.get("rootMountRef"), dict) else None
        restored_context = load_package_entry(str(context_ref.get("locator"))) if context_ref is not None else []
        if not isinstance(restored_context, list):
            restored_context = []
        restored_root_mount = dict(root_mounts)
        snapshot_root_mount = load_package_entry(str(root_mount_ref.get("locator"))) if root_mount_ref is not None else None
        if isinstance(snapshot_root_mount, dict):
            restored_root_mount.update(snapshot_root_mount)
        max_context_items = 12
        restored_context = [item for item in restored_context[:max_context_items] if isinstance(item, dict)]
        protected_items = [
            {"kind": "node", "id": item["id"]}
            for item in restored_context[:4]
            if isinstance(item, dict) and item.get("id") is not None
        ]
        followup_actions = [
            {
                "kind": "resume-checkpoint",
                "snapshotId": task_snapshot.get("id"),
                "resumeToken": task_snapshot.get("resumeToken"),
                "safeStopReason": task_snapshot.get("safeStopReason"),
            }
        ]
        # Forward pending-tool-calls actions so the execution loop can replay them
        snapshot_pending_actions = task_snapshot.get("pendingActions") if isinstance(task_snapshot.get("pendingActions"), list) else []
        request_updates = _restored_request_state([action for action in snapshot_pending_actions if isinstance(action, dict)])
        for action in snapshot_pending_actions:
            if isinstance(action, dict) and action.get("kind") == "pending-tool-calls":
                followup_actions.append(action)
        return {
            "restoredState": {
                "currentContext": restored_context,
                "protectedItems": protected_items,
                "rootMount": restored_root_mount,
                "requestUpdates": request_updates,
            },
            "resumeMessage": task_snapshot.get("resumeMessage") or f"Resume task {task_snapshot.get('taskId') or 'unknown'} from the last safe stop.",
            "followupActions": followup_actions,
            "summary": (
                f"Rehydrated {len(restored_context)} context items from snapshot "
                f"{task_snapshot.get('id') or 'unknown'} and restored {len(request_updates)} runtime request fields."
            ),
        }


plugin = PauseResumeModule()