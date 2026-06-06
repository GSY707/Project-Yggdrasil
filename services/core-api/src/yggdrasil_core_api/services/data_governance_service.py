from ._base import *  # noqa: F403,F401
from yggdrasil_sdk.data_governance import (
    build_deletion_plan,
    data_asset_manifest,
    execute_task_delete,
    list_data_governance_operations,
    record_data_governance_operation,
)
from yggdrasil_sdk.ops_runtime.backup import create_runtime_backup, list_runtime_backups


class DataGovernanceServiceMixin:
    def get_data_governance_manifest(self) -> dict[str, object]:
        return data_asset_manifest(workspace_root=self.workspace_root)

    def list_data_governance_operations(self, *, limit: int = 50) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            operations = list_data_governance_operations(session, limit=limit)
        return {"operations": operations}

    def list_data_governance_backups(self, *, limit: int = 20) -> dict[str, object]:
        return list_runtime_backups(workspace_root=self.workspace_root, limit=limit)

    def create_data_governance_backup(self, payload: dict[str, Any]) -> dict[str, object]:
        requested_by = payload.get("requestedBy") if isinstance(payload.get("requestedBy"), dict) else None
        reason = str(payload.get("reason") or "").strip() or "data-governance-protective-backup"
        snapshot = create_runtime_backup(workspace_root=self.workspace_root)
        with self.runtime.session_scope() as session:
            operation = record_data_governance_operation(
                session,
                operation_type="backup",
                scope_kind="workspace",
                scope_id=None,
                dry_run=False,
                status="completed",
                requested_by=requested_by,
                reason=reason,
                plan=None,
                result={"snapshot": snapshot},
            )
        return {"backup": snapshot, "operation": operation}

    def create_deletion_plan(self, payload: dict[str, Any]) -> dict[str, object]:
        scope_kind = str(payload.get("scopeKind") or "").strip()
        scope_id = str(payload.get("scopeId") or "").strip()
        if not scope_kind or not scope_id:
            raise ValueError("scopeKind and scopeId are required.")
        include_state_files = bool(payload.get("includeStateFiles", True))
        requested_by = payload.get("requestedBy") if isinstance(payload.get("requestedBy"), dict) else None
        reason = str(payload.get("reason") or "").strip() or None
        with self.runtime.session_scope() as session:
            plan = build_deletion_plan(
                session,
                scope_kind,
                scope_id,
                include_state_files=include_state_files,
                workspace_root=self.workspace_root,
            )
            operation = record_data_governance_operation(
                session,
                operation_type="deletion-plan",
                scope_kind=scope_kind,
                scope_id=scope_id,
                dry_run=True,
                status="planned",
                requested_by=requested_by,
                reason=reason,
                plan=plan,
            )
        return {"plan": plan, "operation": operation}

    def execute_deletion_request(self, payload: dict[str, Any]) -> dict[str, object]:
        scope_kind = str(payload.get("scopeKind") or "").strip()
        scope_id = str(payload.get("scopeId") or "").strip()
        confirm_scope_id = str(payload.get("confirmScopeId") or "").strip()
        if not scope_kind or not scope_id:
            raise ValueError("scopeKind and scopeId are required.")
        if confirm_scope_id != scope_id:
            raise ValueError("confirmScopeId must exactly match scopeId.")
        include_state_files = bool(payload.get("includeStateFiles", True))
        backup_before_delete = bool(payload.get("backupBeforeDelete", False))
        requested_by = payload.get("requestedBy") if isinstance(payload.get("requestedBy"), dict) else None
        reason = str(payload.get("reason") or "").strip() or None
        blocked_detail: str | None = None
        backup: dict[str, object] | None = None
        with self.runtime.session_scope() as session:
            preflight_plan = build_deletion_plan(
                session,
                scope_kind,
                scope_id,
                include_state_files=include_state_files,
                workspace_root=self.workspace_root,
            )
            if preflight_plan.get("blockers"):
                blocked_detail = "; ".join(str(item) for item in preflight_plan["blockers"])
                operation = record_data_governance_operation(
                    session,
                    operation_type="delete",
                    scope_kind=scope_kind,
                    scope_id=scope_id,
                    dry_run=False,
                    status="blocked",
                    requested_by=requested_by,
                    reason=reason,
                    plan=preflight_plan,
                    result={"status": "blocked", "error": blocked_detail},
                    error_summary=blocked_detail,
                )
        if blocked_detail is not None:
            raise ValueError(blocked_detail)
        if backup_before_delete:
            backup = create_runtime_backup(workspace_root=self.workspace_root)
        with self.runtime.session_scope() as session:
            plan = build_deletion_plan(
                session,
                scope_kind,
                scope_id,
                include_state_files=include_state_files,
                workspace_root=self.workspace_root,
            )
            try:
                result = execute_task_delete(session, plan, include_state_files=include_state_files)
                if backup is not None:
                    result["backup"] = backup
                    certificate = result.get("deletionCertificate")
                    if isinstance(certificate, dict):
                        certificate["backupSnapshotDir"] = backup.get("snapshotDir")
                status = "completed"
                error_summary = None
            except Exception as exc:
                result = {"status": "blocked", "error": str(exc)}
                if backup is not None:
                    result["backup"] = backup
                status = "blocked"
                error_summary = str(exc)
            operation = record_data_governance_operation(
                session,
                operation_type="delete",
                scope_kind=scope_kind,
                scope_id=scope_id,
                dry_run=False,
                status=status,
                requested_by=requested_by,
                reason=reason,
                plan=plan,
                result=result,
                error_summary=error_summary,
            )
            if status != "completed":
                blocked_detail = error_summary or "Delete request was blocked."
        if blocked_detail is not None:
            raise ValueError(blocked_detail)
        return {"plan": plan, "result": result, "operation": operation}
