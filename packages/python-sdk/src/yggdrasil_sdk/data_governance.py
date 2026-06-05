from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .persistence.orm import (
    AgentRunORM,
    AssetEmbeddingORM,
    AssetORM,
    AssetSegmentORM,
    DataGovernanceOperationORM,
    EdgeORM,
    MailboxMessageORM,
    ModelInvocationORM,
    ModelRouteDecisionORM,
    NodeORM,
    NodeVersionORM,
    OutboxRecordORM,
    PromptCompileArtifactORM,
    RetrievalRequestORM,
    SideChannelEventORM,
    SourceAnnotationORM,
    TaskORM,
    TaskSnapshotORM,
)
from .support import new_id, resolve_state_root, resolve_workspace_root, utc_now


DATA_ASSET_MANIFEST: list[dict[str, object]] = [
    {
        "id": "tasks",
        "label": "Tasks",
        "locations": ["database:tasks", "database:agent_runs", "database:task_snapshots"],
        "deletePolicy": "task-scope-hard-delete-supported",
        "sensitivity": "task-content",
    },
    {
        "id": "runtime",
        "label": "Runtime and model calls",
        "locations": [
            "database:model_route_decisions",
            "database:model_invocations",
            "state:llm/requests",
            "state:llm/responses",
            "state:runtime/window-executions",
            "state:runtime/metrics",
        ],
        "deletePolicy": "task-scope-hard-delete-supported",
        "sensitivity": "task-content-and-provider-metadata",
    },
    {
        "id": "prompt-artifacts",
        "label": "Prompt compile artifacts",
        "locations": ["database:prompt_compile_artifacts", "state:prompt/compiled"],
        "deletePolicy": "task-scope-hard-delete-supported",
        "sensitivity": "prompt-and-context",
    },
    {
        "id": "memory",
        "label": "Nodes and memory graph",
        "locations": ["database:nodes", "database:edges", "database:node_versions", "database:source_annotations"],
        "deletePolicy": "manifest-only-node-hard-delete-pending",
        "sensitivity": "memory-content",
    },
    {
        "id": "assets",
        "label": "Assets and derived segments",
        "locations": ["database:assets", "database:asset_segments", "database:asset_embeddings"],
        "deletePolicy": "manifest-only-asset-hard-delete-pending",
        "sensitivity": "user-content-and-embeddings",
    },
    {
        "id": "mailbox-side-channel",
        "label": "Mailbox, side-channel and outbox",
        "locations": ["database:mailbox_messages", "database:side_channel_events", "database:outbox_records"],
        "deletePolicy": "task-scope-hard-delete-supported",
        "sensitivity": "runtime-coordination",
    },
    {
        "id": "observability",
        "label": "Local and remote observability",
        "locations": ["state:observability", "external:langfuse", "external:otel"],
        "deletePolicy": "local-file-preview-only-remote-delete-pending",
        "sensitivity": "logs-and-trace-metadata",
    },
    {
        "id": "product-logs-backups",
        "label": "Product logs and backups",
        "locations": ["state:product-logs", "workspace:.yggdrasil-backups"],
        "deletePolicy": "warn-only-not-deleted-by-task-delete",
        "sensitivity": "historical-runtime-data",
    },
]


RUNNING_TASK_STATUSES = {"queued", "running", "pause-requested", "restarting"}


def data_asset_manifest(*, workspace_root: Path | None = None) -> dict[str, object]:
    workspace = resolve_workspace_root(workspace_root)
    state_root = resolve_state_root(workspace)
    return {
        "version": "data-governance-manifest-v0.1",
        "generatedAt": utc_now().isoformat(),
        "workspaceRoot": str(workspace),
        "stateRoot": str(state_root),
        "productLogRoot": str(state_root / "product-logs"),
        "backupRoot": str(workspace / ".yggdrasil-backups"),
        "assets": DATA_ASSET_MANIFEST,
        "remoteBoundary": {
            "localModeUploadsToOfficialService": False,
            "remoteDataServiceStatus": "planned",
            "remoteDeleteStatus": "planned",
            "providerBoundary": "LLM providers, Langfuse and remote OTel endpoints are outside local hard-delete unless their own delete APIs are integrated.",
        },
    }


def _ids(session: Session, column: Any, *conditions: Any) -> list[str]:
    statement = sa.select(column)
    for condition in conditions:
        statement = statement.where(condition)
    return [str(value) for value in session.execute(statement).scalars().all()]


def _count(session: Session, model: Any, *conditions: Any) -> int:
    statement = sa.select(sa.func.count()).select_from(model)
    for condition in conditions:
        statement = statement.where(condition)
    return int(session.execute(statement).scalar_one() or 0)


def _in(column: Any, values: Iterable[str]) -> Any:
    normalized = [value for value in values if value]
    return column.in_(normalized) if normalized else sa.false()


def _or_nonempty(*conditions: Any) -> Any:
    usable = [condition for condition in conditions if condition is not None]
    return sa.or_(*usable) if usable else sa.false()


def _table_entry(table: str, count: int, object_ids: list[str], *, action: str) -> dict[str, object]:
    return {
        "table": table,
        "count": count,
        "sampleIds": object_ids[:20],
        "objectIds": object_ids,
        "action": action,
    }


def _locator_from_ref(ref: Any) -> str | None:
    if not isinstance(ref, dict) or str(ref.get("type") or "") != "file":
        return None
    locator = str(ref.get("locator") or "").strip()
    return locator or None


def _safe_file_record(locator: str, *, workspace_root: Path, state_root: Path) -> dict[str, object]:
    candidate = Path(locator)
    path = candidate if candidate.is_absolute() else workspace_root / candidate
    resolved = path.resolve()
    state_resolved = state_root.resolve()
    try:
        safe = resolved.is_relative_to(state_resolved)
    except ValueError:
        safe = False
    exists = resolved.exists()
    return {
        "locator": locator,
        "path": str(resolved),
        "exists": exists,
        "bytes": resolved.stat().st_size if exists and resolved.is_file() else 0,
        "safeToDelete": safe and exists and resolved.is_file(),
        "action": "delete" if safe and exists and resolved.is_file() else "retain",
    }


def _append_ref_file(records: dict[str, dict[str, object]], ref: Any, *, workspace_root: Path, state_root: Path) -> None:
    locator = _locator_from_ref(ref)
    if locator is None:
        return
    record = _safe_file_record(locator, workspace_root=workspace_root, state_root=state_root)
    records[str(record["path"])] = record


def _scan_state_files(
    identifiers: set[str],
    *,
    workspace_root: Path,
    state_root: Path,
    existing: dict[str, dict[str, object]],
) -> None:
    if not identifiers or not state_root.exists():
        return
    scan_roots = [
        state_root / "state" / "llm",
        state_root / "state" / "prompt",
        state_root / "state" / "runtime",
        state_root / "state" / "analysis" / "llm-work",
    ]
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        for path in scan_root.rglob("*"):
            if not path.is_file():
                continue
            haystack = str(path)
            if not any(identifier in haystack for identifier in identifiers):
                continue
            locator = str(path.resolve().relative_to(workspace_root.resolve())) if path.resolve().is_relative_to(workspace_root.resolve()) else str(path.resolve())
            record = _safe_file_record(locator, workspace_root=workspace_root, state_root=state_root)
            existing[str(record["path"])] = record


def build_task_deletion_plan(
    session: Session,
    task_id: str,
    *,
    include_state_files: bool = True,
    workspace_root: Path | None = None,
) -> dict[str, object]:
    task = session.get(TaskORM, task_id)
    if task is None:
        raise KeyError(task_id)

    workspace = resolve_workspace_root(workspace_root)
    state_root = resolve_state_root(workspace)

    run_ids = _ids(session, AgentRunORM.id, AgentRunORM.task_id == task_id)
    snapshot_ids = _ids(session, TaskSnapshotORM.id, TaskSnapshotORM.task_id == task_id)
    route_decision_ids = _ids(
        session,
        ModelRouteDecisionORM.id,
        _or_nonempty(ModelRouteDecisionORM.task_id == task_id, _in(ModelRouteDecisionORM.agent_run_id, run_ids)),
    )
    invocation_ids = _ids(
        session,
        ModelInvocationORM.id,
        _or_nonempty(ModelInvocationORM.task_id == task_id, _in(ModelInvocationORM.agent_run_id, run_ids)),
    )
    prompt_artifact_ids = _ids(
        session,
        PromptCompileArtifactORM.id,
        _or_nonempty(
            PromptCompileArtifactORM.task_id == task_id,
            _in(PromptCompileArtifactORM.agent_run_id, run_ids),
            _in(PromptCompileArtifactORM.model_invocation_id, invocation_ids),
        ),
    )
    mailbox_ids = _ids(session, MailboxMessageORM.id, MailboxMessageORM.task_id == task_id)
    side_channel_ids = _ids(session, SideChannelEventORM.id, SideChannelEventORM.task_id == task_id)
    aggregate_ids = [task_id, *run_ids, *snapshot_ids, *route_decision_ids, *invocation_ids, *prompt_artifact_ids]
    outbox_ids = _ids(session, OutboxRecordORM.id, _in(OutboxRecordORM.aggregate_id, aggregate_ids))

    state_files: dict[str, dict[str, object]] = {}
    if include_state_files:
        for request_ref, response_ref in session.execute(
            sa.select(ModelInvocationORM.request_ref, ModelInvocationORM.response_ref).where(_in(ModelInvocationORM.id, invocation_ids))
        ).all():
            _append_ref_file(state_files, request_ref, workspace_root=workspace, state_root=state_root)
            _append_ref_file(state_files, response_ref, workspace_root=workspace, state_root=state_root)
        for (compiled_messages_ref,) in session.execute(
            sa.select(PromptCompileArtifactORM.compiled_messages_ref).where(_in(PromptCompileArtifactORM.id, prompt_artifact_ids))
        ).all():
            _append_ref_file(state_files, compiled_messages_ref, workspace_root=workspace, state_root=state_root)
        identifiers = {task_id, *run_ids, *snapshot_ids, *invocation_ids, *prompt_artifact_ids}
        _scan_state_files(identifiers, workspace_root=workspace, state_root=state_root, existing=state_files)

    warnings = [
        "本地 task 删除不会自动删除 .yggdrasil-backups；旧备份可能仍包含历史数据。",
        "产品日志不会随 task 删除静默清理；需要单独按日志保留策略处理。",
        "LLM provider、Langfuse、远端 OTel 或未来官方远端服务不受本地删除自动控制。",
    ]
    blockers: list[str] = []
    if task.status in RUNNING_TASK_STATUSES:
        blockers.append(f"Task status is {task.status}; request pause/stop before hard delete.")

    tables = [
        _table_entry("tasks", 1, [task_id], action="delete"),
        _table_entry("agent_runs", len(run_ids), run_ids, action="delete"),
        _table_entry("task_snapshots", len(snapshot_ids), snapshot_ids, action="delete"),
        _table_entry("model_route_decisions", len(route_decision_ids), route_decision_ids, action="delete"),
        _table_entry("model_invocations", len(invocation_ids), invocation_ids, action="delete"),
        _table_entry("prompt_compile_artifacts", len(prompt_artifact_ids), prompt_artifact_ids, action="delete"),
        _table_entry("mailbox_messages", len(mailbox_ids), mailbox_ids, action="delete"),
        _table_entry("side_channel_events", len(side_channel_ids), side_channel_ids, action="delete"),
        _table_entry("outbox_records", len(outbox_ids), outbox_ids, action="delete"),
    ]
    state_file_records = sorted(state_files.values(), key=lambda item: str(item["path"]))
    return {
        "version": "task-deletion-plan-v0.1",
        "generatedAt": utc_now().isoformat(),
        "scopeKind": "task",
        "scopeId": task_id,
        "target": {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "appId": task.app_id,
            "projectId": task.project_id,
        },
        "dryRunOnly": bool(blockers),
        "blockers": blockers,
        "warnings": warnings,
        "database": {
            "tables": tables,
            "totalRows": sum(int(item["count"]) for item in tables),
            "deleteOrder": [
                "outbox_records",
                "prompt_compile_artifacts",
                "model_invocations",
                "model_route_decisions",
                "mailbox_messages",
                "side_channel_events",
                "task_snapshots",
                "agent_runs",
                "tasks",
            ],
            "cascadeNotes": [
                "Runtime child tables are deleted explicitly so SQLite and PostgreSQL keep the same hard-delete outcome.",
                "Prompt artifacts and model invocations are deleted before task rows to break soft-reference cycles.",
            ],
        },
        "stateFiles": state_file_records,
        "stateFileCount": len(state_file_records),
        "stateFileBytes": sum(int(item["bytes"]) for item in state_file_records),
        "retainedData": [
            {"location": str(workspace / ".yggdrasil-backups"), "reason": "backup-retention-policy-not-frozen"},
            {"location": str(state_root / "product-logs"), "reason": "log-retention-policy-not-frozen"},
            {"location": "external providers / Langfuse / OTel", "reason": "external-delete-api-not-integrated"},
        ],
    }


def build_asset_deletion_preview(session: Session, asset_id: str) -> dict[str, object]:
    asset = session.get(AssetORM, asset_id)
    if asset is None:
        raise KeyError(asset_id)
    segment_ids = _ids(session, AssetSegmentORM.id, AssetSegmentORM.asset_id == asset_id)
    embedding_ids = _ids(
        session,
        AssetEmbeddingORM.id,
        _or_nonempty(
            sa.and_(AssetEmbeddingORM.owner_kind == "asset", AssetEmbeddingORM.owner_id == asset_id),
            sa.and_(AssetEmbeddingORM.owner_kind == "asset-segment", _in(AssetEmbeddingORM.owner_id, segment_ids)),
        ),
    )
    return {
        "version": "asset-deletion-preview-v0.1",
        "generatedAt": utc_now().isoformat(),
        "scopeKind": "asset",
        "scopeId": asset_id,
        "target": {"id": asset.id, "mediaType": asset.media_type, "role": asset.role, "storageKey": asset.storage_key},
        "dryRunOnly": True,
        "blockers": ["Asset hard delete is not enabled in this phase."],
        "database": {
            "tables": [
                _table_entry("assets", 1, [asset_id], action="planned"),
                _table_entry("asset_segments", len(segment_ids), segment_ids, action="planned"),
                _table_entry("asset_embeddings", len(embedding_ids), embedding_ids, action="planned"),
            ],
        },
        "warnings": ["Asset storage keys and embedding vector refs need a frozen file/object-store deletion policy before execution."],
    }


def build_node_deletion_preview(session: Session, node_id: str) -> dict[str, object]:
    node = session.get(NodeORM, node_id)
    if node is None:
        raise KeyError(node_id)
    child_ids = _ids(session, NodeORM.id, NodeORM.parent_id == node_id)
    version_ids = _ids(session, NodeVersionORM.id, NodeVersionORM.node_id == node_id)
    edge_ids = _ids(session, EdgeORM.id, sa.or_(EdgeORM.from_node_id == node_id, EdgeORM.to_node_id == node_id))
    annotation_ids = _ids(session, SourceAnnotationORM.id, SourceAnnotationORM.owner_kind == "node", SourceAnnotationORM.owner_id == node_id)
    retrieval_ids = _ids(session, RetrievalRequestORM.id, RetrievalRequestORM.work_tree_node_id == node_id)
    return {
        "version": "node-deletion-preview-v0.1",
        "generatedAt": utc_now().isoformat(),
        "scopeKind": "node",
        "scopeId": node_id,
        "target": {"id": node.id, "title": node.title, "status": node.status, "nodeType": node.node_type},
        "dryRunOnly": True,
        "blockers": ["Node hard delete is not enabled in this phase; soft forgetting is not a deletion proof."],
        "database": {
            "tables": [
                _table_entry("nodes", 1, [node_id], action="planned"),
                _table_entry("node_children", len(child_ids), child_ids, action="needs-policy"),
                _table_entry("node_versions", len(version_ids), version_ids, action="planned"),
                _table_entry("edges", len(edge_ids), edge_ids, action="planned"),
                _table_entry("source_annotations", len(annotation_ids), annotation_ids, action="planned"),
                _table_entry("retrieval_requests", len(retrieval_ids), retrieval_ids, action="planned"),
            ],
        },
        "warnings": ["Node subtree, relation repair and audit-summary retention policy must be frozen before execution."],
    }


def build_deletion_plan(
    session: Session,
    scope_kind: str,
    scope_id: str,
    *,
    include_state_files: bool = True,
    workspace_root: Path | None = None,
) -> dict[str, object]:
    normalized = scope_kind.strip().lower()
    if normalized == "task":
        return build_task_deletion_plan(session, scope_id, include_state_files=include_state_files, workspace_root=workspace_root)
    if normalized == "asset":
        return build_asset_deletion_preview(session, scope_id)
    if normalized == "node":
        return build_node_deletion_preview(session, scope_id)
    raise ValueError("scopeKind must be one of: task, asset, node.")


def _delete_state_files(plan: dict[str, object]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for item in plan.get("stateFiles") or []:
        if not isinstance(item, dict) or not bool(item.get("safeToDelete")):
            continue
        path = Path(str(item.get("path") or ""))
        try:
            path.unlink()
            results.append({"path": str(path), "status": "deleted"})
        except FileNotFoundError:
            results.append({"path": str(path), "status": "already-missing"})
        except Exception as exc:
            results.append({"path": str(path), "status": "failed", "error": str(exc)})
    return results


def execute_task_delete(session: Session, plan: dict[str, object], *, include_state_files: bool = True) -> dict[str, object]:
    if plan.get("scopeKind") != "task":
        raise ValueError("Only task hard delete is enabled in this phase.")
    if plan.get("blockers"):
        raise ValueError("; ".join(str(item) for item in plan["blockers"]))

    table_ids = {
        str(item["table"]): [str(value) for value in item.get("objectIds") or []]
        for item in plan.get("database", {}).get("tables", [])
        if isinstance(item, dict)
    }
    prompt_ids = table_ids.get("prompt_compile_artifacts", [])
    invocation_ids = table_ids.get("model_invocations", [])
    route_decision_ids = table_ids.get("model_route_decisions", [])
    outbox_ids = table_ids.get("outbox_records", [])
    mailbox_ids = table_ids.get("mailbox_messages", [])
    side_channel_ids = table_ids.get("side_channel_events", [])
    snapshot_ids = table_ids.get("task_snapshots", [])
    agent_run_ids = table_ids.get("agent_runs", [])
    task_ids = table_ids.get("tasks", [])

    if prompt_ids:
        session.execute(
            sa.update(ModelInvocationORM)
            .where(_in(ModelInvocationORM.prompt_compile_artifact_id, prompt_ids))
            .values(prompt_compile_artifact_id=None)
        )
        session.execute(sa.delete(PromptCompileArtifactORM).where(_in(PromptCompileArtifactORM.id, prompt_ids)))
    if invocation_ids:
        session.execute(sa.delete(ModelInvocationORM).where(_in(ModelInvocationORM.id, invocation_ids)))
    if route_decision_ids:
        session.execute(sa.delete(ModelRouteDecisionORM).where(_in(ModelRouteDecisionORM.id, route_decision_ids)))
    if outbox_ids:
        session.execute(sa.delete(OutboxRecordORM).where(_in(OutboxRecordORM.id, outbox_ids)))
    if mailbox_ids:
        session.execute(sa.delete(MailboxMessageORM).where(_in(MailboxMessageORM.id, mailbox_ids)))
    if side_channel_ids:
        session.execute(sa.delete(SideChannelEventORM).where(_in(SideChannelEventORM.id, side_channel_ids)))
    if snapshot_ids:
        session.execute(sa.delete(TaskSnapshotORM).where(_in(TaskSnapshotORM.id, snapshot_ids)))
    if agent_run_ids:
        session.execute(sa.delete(AgentRunORM).where(_in(AgentRunORM.id, agent_run_ids)))
    for task_id in task_ids:
        task = session.get(TaskORM, task_id)
        if task is not None:
            session.delete(task)
    session.flush()

    file_results = _delete_state_files(plan) if include_state_files else []
    return {
        "status": "completed",
        "executedAt": utc_now().isoformat(),
        "deletedRows": int(plan.get("database", {}).get("totalRows") or 0),
        "stateFiles": file_results,
        "retainedData": plan.get("retainedData") or [],
    }


def record_data_governance_operation(
    session: Session,
    *,
    operation_type: str,
    scope_kind: str,
    scope_id: str | None,
    dry_run: bool,
    status: str,
    requested_by: dict[str, object] | None,
    reason: str | None,
    plan: dict[str, object] | None,
    result: dict[str, object] | None = None,
    error_summary: str | None = None,
) -> dict[str, object]:
    now = utc_now()
    record = DataGovernanceOperationORM(
        id=new_id("data-governance-operation", operation_type, scope_kind, scope_id or "", now.isoformat()),
        operation_type=operation_type,
        scope_kind=scope_kind,
        scope_id=scope_id,
        dry_run=dry_run,
        status=status,
        plan_ref=plan,
        result_ref=result,
        requested_by=requested_by or {"type": "user", "id": "web"},
        reason=reason,
        created_at=now,
        executed_at=now if not dry_run and status in {"completed", "blocked", "failed"} else None,
        error_summary=error_summary,
    )
    session.add(record)
    session.flush()
    return data_governance_operation_record(record)


def data_governance_operation_record(model: DataGovernanceOperationORM) -> dict[str, object]:
    return {
        "id": model.id,
        "operationType": model.operation_type,
        "scopeKind": model.scope_kind,
        "scopeId": model.scope_id,
        "dryRun": model.dry_run,
        "status": model.status,
        "plan": model.plan_ref,
        "result": model.result_ref,
        "requestedBy": model.requested_by,
        "reason": model.reason,
        "createdAt": model.created_at.isoformat(),
        "executedAt": model.executed_at.isoformat() if model.executed_at else None,
        "errorSummary": model.error_summary,
    }


def list_data_governance_operations(session: Session, *, limit: int = 50) -> list[dict[str, object]]:
    statement = sa.select(DataGovernanceOperationORM).order_by(DataGovernanceOperationORM.created_at.desc()).limit(limit)
    return [data_governance_operation_record(record) for record in session.execute(statement).scalars().all()]
