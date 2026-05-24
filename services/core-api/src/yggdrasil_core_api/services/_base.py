from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import sqlalchemy as sa

from yggdrasil_sdk import (
    active_application_id,
    ActorRef,
    AssetRepository,
    CollaborationRepository,
    build_application_catalog_snapshot,
    compile_runtime_prompt,
    ensure_mcp_bridge_config,
    EvaluationRepository,
    EventEnvelope,
    ensure_evaluation_suites,
    mcp_bridge_overview,
    get_application_config_binding,
    get_application_manifest,
    HookNames,
    list_evaluation_suite_definitions,
    list_prompt_profile_definitions,
    list_registered_agent_tools,
    list_seed_template_definitions,
    load_effective_application_config,
    refresh_copyable_mcp_servers,
    MemoryRepository,
    NodeRepository,
    OutboxRepository,
    PromptAssetRepository,
    resolve_application_active_capabilities,
    RedisCoordinator,
    RetrievalBundle,
    RuntimeRepository,
    run_evaluation_suite,
    set_mcp_bridge_server_enabled,
    summarize_observability,
    sync_mcp_bridge_servers,
    TaskRepository,
    TrainingRepository,
    ensure_workspace_bootstrap,
    get_persistence_runtime,
    load_in_process_plugin,
    update_mcp_bridge_workspace,
    new_id,
    set_active_application,
    sync_module_catalog_snapshot,
    utc_now,
    upsert_mcp_bridge_server,
    upsert_application_config_binding,
)
from yggdrasil_sdk.collaboration_runtime import create_pull_request as create_collaboration_pull_request
from yggdrasil_sdk.collaboration_runtime import launch_subagent_task, review_pull_request as review_collaboration_pull_request
from yggdrasil_sdk.persistence.orm import (
    ImportJobORM,
    MemoryBranchORM,
    ModelInvocationORM,
    NodeORM,
    OutboxRecordORM,
    PermissionTupleORM,
    PullRequestORM,
    RetrievalRequestORM,
    SpaceMountORM,
    SpaceORM,
    TaskORM,
    TaskSnapshotORM,
)
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel import approve_task_completion as approve_runtime_task_completion
from yggdrasil_sdk.runtime_kernel import post_task_mailbox_message as post_runtime_task_mailbox_message
from yggdrasil_sdk.runtime_kernel import queue_main_agent_execution as queue_runtime_task_execution
from yggdrasil_sdk.runtime_kernel import record_task_side_channel_event as post_runtime_side_channel_event
from yggdrasil_sdk.runtime_kernel import request_task_revision as request_runtime_task_revision
from yggdrasil_sdk.runtime_kernel import request_task_pause as request_runtime_task_pause
from yggdrasil_sdk.runtime_kernel.takeover import load_persisted_task_takeover_protocol
from yggdrasil_sdk.support import read_json




class WorkspaceServiceBase:
    def __init__(self, workspace_root: Path | None = None) -> None:
        self.workspace_root = workspace_root
        self.runtime = get_persistence_runtime()
        self.coordinator = RedisCoordinator(self.runtime.settings)

    def _status_counts(self, session, orm_model, status_column) -> dict[str, int]:
        statement = sa.select(status_column, sa.func.count()).group_by(status_column)
        return {
            str(status): int(count)
            for status, count in session.execute(statement).all()
            if status is not None
        }

    def _scalar_count(self, session, orm_model, where_clause=None) -> int:
        statement = sa.select(sa.func.count()).select_from(orm_model)
        if where_clause is not None:
            statement = statement.where(where_clause)
        value = session.execute(statement).scalar_one()
        return int(value or 0)

    def _resolve_locator_path(self, locator: str | None) -> Path | None:
        if not locator:
            return None
        candidate = Path(locator)
        if candidate.is_absolute():
            return candidate
        if self.workspace_root is not None:
            return self.workspace_root / candidate
        return candidate

    def _load_ref_payload(self, locator: str | None) -> Any:
        path = self._resolve_locator_path(locator)
        if path is None:
            return None
        return read_json(path, None)

    def _load_metrics_payload(self, locator: str | None) -> dict[str, Any] | None:
        payload = self._load_ref_payload(locator)
        return payload if isinstance(payload, dict) else None

    def _load_jsonl_preview(self, locator: str | None, *, limit: int = 3) -> list[Any]:
        path = self._resolve_locator_path(locator)
        if path is None or not path.exists():
            return []
        rows: list[Any] = []
        for line in path.read_text(encoding="utf-8").splitlines()[:limit]:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError:
                rows.append(stripped)
        return rows

    def _load_module(self, module_id: str) -> tuple[Any, Any, Any]:
        snapshot = sync_module_catalog_snapshot(self.workspace_root)
        manifests_by_module_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
        installs_by_module_id = {record.module_id: record for record in snapshot.installs}
        manifest = manifests_by_module_id.get(module_id)
        install = installs_by_module_id.get(module_id)
        if manifest is None or install is None or not manifest.entry_point:
            raise KeyError(f"Module not available: {module_id}")
        if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded"}:
            raise RuntimeError(f"Module {module_id} is not active.")
        plugin = load_in_process_plugin(manifest.entry_point)
        return plugin, manifest, install

    def _call_module_hook(self, module_id: str, hook_name: str, payload: dict[str, object]) -> dict[str, object]:
        plugin, _, _ = self._load_module(module_id)
        for registration in plugin.register_hooks():
            if registration.name != hook_name:
                continue
            result = registration.handler(payload)
            if result is None:
                return {}
            if isinstance(result, dict):
                return result
            return {"items": list(result)}
        raise KeyError(f"Hook {hook_name} not exported by {module_id}.")

    def _dispatch_module_event(self, module_id: str, envelope: EventEnvelope) -> Any:
        plugin, _, _ = self._load_module(module_id)
        return plugin.handle_event(envelope)

    def _record_package_event(
        self,
        session,
        *,
        project_id: str | None,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        locator: str,
    ):
        return OutboxRepository(session).record_event(
            {
                "projectId": project_id,
                "aggregateType": aggregate_type,
                "aggregateId": aggregate_id,
                "eventType": event_type,
                "payloadRef": {"type": "package-entry", "locator": locator},
            }
        )

    def _materialize_tree_plan(self, session, *, import_job, tree_plan) -> dict[str, object]:
        repository = NodeRepository(session)
        actor = {"type": "module", "id": "text-memory"}
        nodes: list[dict[str, object]] = []
        edges: list[dict[str, object]] = []
        annotations: list[dict[str, object]] = []
        outbox_records: list[dict[str, object]] = []

        for node_payload in tree_plan.candidate_node_payloads:
            node_id = str(node_payload.get("id"))
            node = repository.get_node(node_id)
            if node is None:
                node = repository.create_node(
                    {
                        **node_payload,
                        "projectId": import_job.project_id,
                        "branchId": import_job.branch_id,
                        "createdBy": node_payload.get("createdBy") or actor,
                        "updatedBy": node_payload.get("updatedBy") or actor,
                        "changeReason": "import-materialize",
                    }
                )
                outbox_record = self._record_package_event(
                    session,
                    project_id=import_job.project_id,
                    aggregate_type="node",
                    aggregate_id=node.id,
                    event_type="node.created",
                    locator=f"core-api/nodes/{node.id}",
                )
                outbox_records.append(outbox_record.model_dump(by_alias=True, mode="json"))
            nodes.append(node.model_dump(by_alias=True, mode="json"))

        for annotation_payload in tree_plan.candidate_source_annotations:
            annotation_id = str(annotation_payload.get("id")) if annotation_payload.get("id") is not None else None
            annotation = repository.get_source_annotation(annotation_id) if annotation_id is not None else None
            if annotation is None:
                annotation = repository.add_source_annotation(
                    str(annotation_payload.get("ownerKind") or "node"),
                    str(annotation_payload.get("ownerId")),
                    {
                        **annotation_payload,
                        "projectId": import_job.project_id,
                        "branchId": import_job.branch_id,
                        "createdBy": annotation_payload.get("createdBy") or actor,
                    },
                )
                outbox_record = self._record_package_event(
                    session,
                    project_id=import_job.project_id,
                    aggregate_type="source-annotation",
                    aggregate_id=annotation.id,
                    event_type="source.annotation.recorded",
                    locator=f"core-api/memory/source-annotations/{annotation.id}",
                )
                outbox_records.append(outbox_record.model_dump(by_alias=True, mode="json"))
            annotations.append(annotation.model_dump(by_alias=True, mode="json"))

        for edge_payload in tree_plan.candidate_edge_payloads:
            edge_id = str(edge_payload.get("id")) if edge_payload.get("id") is not None else None
            edge = repository.get_edge(edge_id) if edge_id is not None else None
            if edge is None:
                edge = repository.create_edge(
                    {
                        **edge_payload,
                        "projectId": import_job.project_id,
                        "branchId": import_job.branch_id,
                        "createdBy": edge_payload.get("createdBy") or actor,
                        "updatedBy": edge_payload.get("updatedBy") or actor,
                    }
                )
                outbox_record = self._record_package_event(
                    session,
                    project_id=import_job.project_id,
                    aggregate_type="edge",
                    aggregate_id=edge.id,
                    event_type="edge.created",
                    locator=f"core-api/memory/edges/{edge.id}",
                )
                outbox_records.append(outbox_record.model_dump(by_alias=True, mode="json"))
            edges.append(edge.model_dump(by_alias=True, mode="json"))

        return {
            "nodes": nodes,
            "edges": edges,
            "sourceAnnotations": annotations,
            "outboxRecords": outbox_records,
        }

