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
from yggdrasil_sdk.runtime_kernel import queue_main_agent_execution as queue_runtime_task_execution
from yggdrasil_sdk.runtime_kernel import request_task_pause as request_runtime_task_pause
from yggdrasil_sdk.support import read_json


class WorkspaceService:
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

    def health_report(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "core-api",
            "database": self.runtime.ping_database(),
            "redis": self.coordinator.ping(),
        }

    def _llm_summary(self, session) -> dict[str, object]:
        status_counts = self._status_counts(session, ModelInvocationORM, ModelInvocationORM.status)
        total_invocations = sum(status_counts.values())
        total_cost = session.execute(sa.select(sa.func.coalesce(sa.func.sum(ModelInvocationORM.cost_used), 0.0))).scalar_one()
        total_input_tokens = session.execute(sa.select(sa.func.coalesce(sa.func.sum(ModelInvocationORM.input_tokens_used), 0))).scalar_one()
        total_output_tokens = session.execute(sa.select(sa.func.coalesce(sa.func.sum(ModelInvocationORM.output_tokens_used), 0))).scalar_one()
        provider_label = sa.func.coalesce(ModelInvocationORM.resolved_provider, ModelInvocationORM.requested_provider, "unknown")
        provider_counts = {
            str(provider or "unknown"): int(count)
            for provider, count in session.execute(sa.select(provider_label, sa.func.count()).group_by(provider_label)).all()
        }
        return {
            "totalInvocations": total_invocations,
            "liveInvocations": int(status_counts.get("completed", 0)),
            "fallbackInvocations": int(status_counts.get("fallback", 0)),
            "failedInvocations": int(status_counts.get("failed", 0)),
            "totalCostUsed": round(float(total_cost or 0.0), 6),
            "totalInputTokens": int(total_input_tokens or 0),
            "totalOutputTokens": int(total_output_tokens or 0),
            "providerCounts": provider_counts,
            "statusCounts": status_counts,
        }

    def _task_runtime_control_summary(self, task, snapshots: list[Any]) -> dict[str, object]:
        latest_snapshot = snapshots[0] if snapshots else None
        latest_restorable_snapshot = next((snapshot for snapshot in snapshots if snapshot.status == "restorable"), None)
        restorable_count = len([snapshot for snapshot in snapshots if snapshot.status == "restorable"])
        consumed_count = len([snapshot for snapshot in snapshots if snapshot.status == "consumed"])

        if task.status == "paused" and latest_restorable_snapshot is not None:
            resume_status = "ready"
        elif task.status == "pause-requested":
            resume_status = "awaiting-safe-stop"
        elif latest_restorable_snapshot is not None:
            resume_status = "snapshot-present"
        else:
            resume_status = "unavailable"

        return {
            "pauseRequested": bool(task.pause_requested),
            "activeSnapshotId": task.active_snapshot_id,
            "lastSafeStopAt": task.last_safe_stop_at,
            "snapshotCount": len(snapshots),
            "restorableSnapshotCount": restorable_count,
            "consumedSnapshotCount": consumed_count,
            "resumeStatus": resume_status,
            "canResume": bool(task.status == "paused" and latest_restorable_snapshot is not None),
            "canRequestPause": bool(task.status in {"queued", "running", "pause-requested"}),
            "recommendedResumeToken": latest_restorable_snapshot.resume_token if latest_restorable_snapshot is not None else None,
            "recommendedResumeMessage": (
                latest_restorable_snapshot.resume_message
                if latest_restorable_snapshot is not None
                else task.resume_message
            ),
            "latestSnapshot": latest_snapshot.model_dump(by_alias=True, mode="json") if latest_snapshot is not None else None,
            "latestRestorableSnapshot": (
                latest_restorable_snapshot.model_dump(by_alias=True, mode="json")
                if latest_restorable_snapshot is not None
                else None
            ),
        }

    def get_observability_summary(self, *, limit: int = 60) -> dict[str, object]:
        summary = summarize_observability(limit=limit, workspace_root=self.workspace_root)
        summary["health"] = self.health_report()
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            runtime_repository = RuntimeRepository(session)
            summary["llmSummary"] = self._llm_summary(session)
            summary["recentModelInvocations"] = [
                invocation.model_dump(by_alias=True, mode="json")
                for invocation in runtime_repository.list_model_invocations(limit=min(limit, 20))
            ]
        return summary

    def list_evaluation_suites(self) -> dict[str, object]:
        definitions = {
            str(definition.get("id")): definition
            for definition in list_evaluation_suite_definitions(self.workspace_root)
        }
        ensure_evaluation_suites(self.workspace_root)
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            suites = EvaluationRepository(session).list_suites(limit=200)
        return {
            "evaluationSuites": [
                {
                    **suite.model_dump(by_alias=True, mode="json"),
                    "caseCount": len(definitions.get(suite.id, {}).get("cases") or []),
                    "cases": list(definitions.get(suite.id, {}).get("cases") or []),
                    "subjectKind": definitions.get(suite.id, {}).get("subjectKind", "workflow"),
                    "subjectRef": definitions.get(suite.id, {}).get("subjectRef", suite.id),
                }
                for suite in suites
            ]
        }

    def list_evaluation_runs(
        self,
        *,
        suite_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        ensure_evaluation_suites(self.workspace_root)
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            runs = EvaluationRepository(session).list_runs(suite_id=suite_id, status=status, limit=limit)
        return {
            "evaluationRuns": [
                {
                    **run.model_dump(by_alias=True, mode="json"),
                    "metrics": self._load_metrics_payload(run.metrics_ref.locator if run.metrics_ref else None),
                }
                for run in runs
            ]
        }

    def execute_evaluation_suite(self, suite_id: str) -> dict[str, object]:
        return run_evaluation_suite(suite_id, self.workspace_root)

    def list_assets(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        branch_id: str | None = None,
        owner_node_id: str | None = None,
        media_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            assets = AssetRepository(session).list_assets(
                project_id=project_id,
                space_id=space_id,
                branch_id=branch_id,
                owner_node_id=owner_node_id,
                media_type=media_type,
                limit=limit,
            )
        return {"assets": [asset.model_dump(by_alias=True, mode="json") for asset in assets]}

    def get_asset(self, asset_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = AssetRepository(session)
            asset = repository.get_asset(asset_id)
            if asset is None:
                raise KeyError(asset_id)
            segments = repository.list_asset_segments(asset_id, limit=1000)
            segment_ids = {segment.id for segment in segments}
            embeddings = [
                embedding
                for embedding in repository.list_embeddings(owner_kind="asset-segment", limit=max(len(segment_ids) * 4, 200))
                if embedding.owner_id in segment_ids
            ]
            asset_embeddings = repository.list_embeddings(owner_kind="asset", owner_id=asset_id, limit=100)
        return {
            "asset": asset.model_dump(by_alias=True, mode="json"),
            "segments": [segment.model_dump(by_alias=True, mode="json") for segment in segments],
            "embeddings": [embedding.model_dump(by_alias=True, mode="json") for embedding in [*asset_embeddings, *embeddings]],
            "sourcePayload": self._load_ref_payload(asset.source_ref.locator if asset.source_ref else None),
        }

    def ingest_asset(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule

        result = MultimodalMemoryModule().ingest_asset(payload)
        return result

    def list_dataset_versions(
        self,
        *,
        dataset_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            versions = TrainingRepository(session).list_dataset_versions(dataset_name=dataset_name, limit=limit)
        return {"datasetVersions": [version.model_dump(by_alias=True, mode="json") for version in versions]}

    def get_dataset_version(self, dataset_version_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = TrainingRepository(session)
            dataset_version = repository.get_dataset_version(dataset_version_id)
            if dataset_version is None:
                raise KeyError(dataset_version_id)
            model_artifacts = repository.list_model_artifacts(dataset_version_id=dataset_version_id, limit=200)
        return {
            "datasetVersion": dataset_version.model_dump(by_alias=True, mode="json"),
            "modelArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in model_artifacts],
            "previewRows": self._load_jsonl_preview(dataset_version.storage_key, limit=5),
        }

    def prepare_dataset_version(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_training_lab.plugin import TrainingLabModule

        return TrainingLabModule().prepare_dataset(payload)

    def list_model_artifacts(
        self,
        *,
        dataset_version_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            artifacts = TrainingRepository(session).list_model_artifacts(
                dataset_version_id=dataset_version_id,
                status=status,
                limit=limit,
            )
        return {"modelArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in artifacts]}

    def get_model_artifact(self, artifact_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = TrainingRepository(session)
            artifact = repository.get_model_artifact(artifact_id)
            if artifact is None:
                raise KeyError(artifact_id)
            dataset_version = repository.get_dataset_version(artifact.dataset_version_id)
        return {
            "modelArtifact": artifact.model_dump(by_alias=True, mode="json"),
            "datasetVersion": dataset_version.model_dump(by_alias=True, mode="json") if dataset_version is not None else None,
            "metrics": self._load_metrics_payload(artifact.metrics_ref.locator if artifact.metrics_ref else None),
        }

    def stage_model_artifact(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_training_lab.plugin import TrainingLabModule

        return TrainingLabModule().stage_model_artifact(payload)

    def list_prompt_profiles(
        self,
        app_id: str | None = None,
        active_capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        return {
            "appId": resolved_app_id,
            "promptProfiles": [
                profile.model_dump(by_alias=True, mode="json")
                for profile in list_prompt_profile_definitions(resolved_app_id, active_capabilities)
            ]
        }

    def list_seed_templates(
        self,
        app_id: str | None = None,
        active_capabilities: list[str] | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        return {
            "appId": resolved_app_id,
            "seedTemplates": [
                template.model_dump(by_alias=True, mode="json")
                for template in list_seed_template_definitions(resolved_app_id, active_capabilities)
            ]
        }

    def list_registered_prompt_tools(
        self,
        active_capabilities: list[str] | None = None,
        app_id: str | None = None,
    ) -> dict[str, object]:
        resolved_app_id = app_id or active_application_id(self.workspace_root)
        resolved_capabilities = active_capabilities or resolve_application_active_capabilities(
            app_id=resolved_app_id,
            workspace_root=self.workspace_root,
        )
        return {
            "appId": resolved_app_id,
            "activeCapabilities": list(resolved_capabilities or []),
            "registeredTools": list_registered_agent_tools(resolved_capabilities),
        }

    def list_prompt_compile_artifacts(
        self,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        app_id: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            artifacts = PromptAssetRepository(session).list_prompt_compile_artifacts(
                project_id=project_id,
                task_id=task_id,
                app_id=app_id,
                limit=limit,
            )
        return {
            "promptCompileArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in artifacts]
        }

    def get_prompt_compile_artifact(self, artifact_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            prompt_repository = PromptAssetRepository(session)
            runtime_repository = RuntimeRepository(session)
            artifact = prompt_repository.get_prompt_compile_artifact(artifact_id)
            if artifact is None:
                raise KeyError(artifact_id)
            linked_invocation = next(
                (
                    invocation
                    for invocation in runtime_repository.list_model_invocations(app_id=artifact.app_id, limit=200)
                    if invocation.id == artifact.model_invocation_id or invocation.prompt_compile_artifact_id == artifact.id
                ),
                None,
            )
        return {
            "promptCompileArtifact": artifact.model_dump(by_alias=True, mode="json"),
            "compiledMessages": self._load_ref_payload(artifact.compiled_messages_ref.locator if artifact.compiled_messages_ref else None),
            "modelInvocation": linked_invocation.model_dump(by_alias=True, mode="json") if linked_invocation is not None else None,
            "requestPayload": self._load_ref_payload(linked_invocation.request_ref.locator if linked_invocation and linked_invocation.request_ref else None),
            "responsePayload": self._load_ref_payload(linked_invocation.response_ref.locator if linked_invocation and linked_invocation.response_ref else None),
        }

    def compile_prompt_preview(self, payload: dict[str, Any]) -> dict[str, object]:
        task_payload = payload.get("task") if isinstance(payload.get("task"), dict) else {}
        request_payload = payload.get("request") if isinstance(payload.get("request"), dict) else {}
        root_mount_payload = payload.get("rootMount") if isinstance(payload.get("rootMount"), dict) else {}
        app_id = str(payload.get("appId") or request_payload.get("appId") or active_application_id(self.workspace_root))
        try:
            effective_config = load_effective_application_config(app_id, self.workspace_root)
        except KeyError as exc:
            raise ValueError(f"Unknown application: {app_id}") from exc
        preview_defaults = effective_config.get("promptPreviewDefaults") if isinstance(effective_config.get("promptPreviewDefaults"), dict) else {}
        run_type = str(payload.get("runType") or effective_config.get("defaultRunType") or "main")
        task_type = str(payload.get("taskType") or effective_config.get("defaultTaskType") or "generic")
        active_capabilities = [
            str(item)
            for item in (
                payload.get("activeCapabilities")
                or root_mount_payload.get("activeCapabilities")
                or effective_config.get("defaultCapabilities")
                or []
            )
            if str(item).strip()
        ]
        request_payload = {**request_payload, "appId": app_id}
        if not request_payload.get("responseRequirements") and preview_defaults.get("responseRequirements"):
            request_payload["responseRequirements"] = str(preview_defaults["responseRequirements"])
        task = SimpleNamespace(
            title=str(task_payload.get("title") or "Prompt Control Preview"),
            goal=str(task_payload.get("goal") or "Preview the compiled runtime prompt."),
            current_focus=str(task_payload.get("currentFocus") or request_payload.get("currentFocus") or "prompt-ops"),
            current_objective=str(task_payload.get("currentObjective") or request_payload.get("currentObjective") or task_payload.get("goal") or "preview compile"),
            resume_message=str(task_payload.get("resumeMessage") or request_payload.get("resumeMessage") or ""),
            app_id=app_id,
        )
        root_mount = {
            "systemIntro": str(root_mount_payload.get("systemIntro") or "Prompt compile preview"),
            "rootSummary": str(root_mount_payload.get("rootSummary") or "Use the same prompt compiler that the runtime persists into prompt artifacts."),
            "taskObjective": str(root_mount_payload.get("taskObjective") or request_payload.get("currentObjective") or task.goal),
            "resumeMessage": str(root_mount_payload.get("resumeMessage") or task.resume_message),
            "mountedNodeRefs": list(root_mount_payload.get("mountedNodeRefs") or []),
            "accessibleMounts": list(root_mount_payload.get("accessibleMounts") or []),
            "activeCapabilities": active_capabilities,
        }
        current_context = [
            dict(item)
            for item in payload.get("currentContext") or []
            if isinstance(item, dict)
        ]
        compiled = compile_runtime_prompt(
            task=task,
            run_type=run_type,
            task_type=task_type,
            root_mount=root_mount,
            current_context=current_context,
            request=request_payload,
            resume_path=str(payload.get("resumePath")) if payload.get("resumePath") is not None else None,
        )
        return {
            "appId": app_id,
            "compiledPrompt": compiled.model_dump(by_alias=True, mode="json"),
            "registeredTools": compiled.registered_tools,
        }

    def list_applications(self) -> dict[str, object]:
        snapshot = build_application_catalog_snapshot(self.workspace_root)
        active_app_id = active_application_id(self.workspace_root)
        applications = []
        for manifest in snapshot.manifests:
            binding = get_application_config_binding(manifest.app_id, self.workspace_root)
            applications.append(
                {
                    "application": manifest.model_dump(by_alias=True, mode="json"),
                    "configBinding": binding.model_dump(by_alias=True, mode="json"),
                }
            )
        return {
            "activeAppId": active_app_id,
            "applications": applications,
        }

    def get_application(self, app_id: str) -> dict[str, object]:
        manifest = get_application_manifest(app_id, self.workspace_root)
        binding = get_application_config_binding(app_id, self.workspace_root)
        return {
            "application": manifest.model_dump(by_alias=True, mode="json"),
            "configBinding": binding.model_dump(by_alias=True, mode="json"),
            "effectiveConfig": load_effective_application_config(app_id, self.workspace_root),
            "dashboard": self._load_ref_payload(manifest.dashboard_ref.locator if manifest.dashboard_ref else None),
        }

    def activate_application(self, app_id: str) -> dict[str, object]:
        binding = set_active_application(app_id, self.workspace_root)
        manifest = get_application_manifest(app_id, self.workspace_root)
        return {
            "application": manifest.model_dump(by_alias=True, mode="json"),
            "configBinding": binding.model_dump(by_alias=True, mode="json"),
            "effectiveConfig": load_effective_application_config(app_id, self.workspace_root),
        }

    def update_application_config(self, app_id: str, payload: dict[str, Any]) -> dict[str, object]:
        important_config = payload.get("importantConfig") if isinstance(payload.get("importantConfig"), dict) else payload
        binding = upsert_application_config_binding(app_id, dict(important_config or {}), self.workspace_root)
        manifest = get_application_manifest(app_id, self.workspace_root)
        return {
            "application": manifest.model_dump(by_alias=True, mode="json"),
            "configBinding": binding.model_dump(by_alias=True, mode="json"),
            "effectiveConfig": load_effective_application_config(app_id, self.workspace_root),
        }

    def get_mcp_bridge_state(self) -> dict[str, object]:
        ensure_mcp_bridge_config(self.workspace_root)
        state = mcp_bridge_overview(self.workspace_root)
        if not state.get("syncedServers"):
            sync_mcp_bridge_servers(self.workspace_root)
            state = mcp_bridge_overview(self.workspace_root)
        return state

    def refresh_mcp_bridge_imports(self) -> dict[str, object]:
        refresh_copyable_mcp_servers(self.workspace_root)
        return self.get_mcp_bridge_state()

    def sync_mcp_bridge(self, payload: dict[str, Any] | None = None) -> dict[str, object]:
        request = payload or {}
        server_ids = [
            str(item)
            for item in request.get("serverIds") or []
            if str(item).strip()
        ]
        sync_mcp_bridge_servers(self.workspace_root, server_ids=server_ids or None)
        return self.get_mcp_bridge_state()

    def update_mcp_bridge_workspace(self, payload: dict[str, Any]) -> dict[str, object]:
        project_workspace = str(payload.get("projectWorkspace") or "").strip()
        if not project_workspace:
            raise ValueError("projectWorkspace is required.")
        update_mcp_bridge_workspace(project_workspace, self.workspace_root)
        return self.get_mcp_bridge_state()

    def upsert_mcp_bridge_server(self, payload: dict[str, Any]) -> dict[str, object]:
        upsert_mcp_bridge_server(payload, self.workspace_root)
        return self.get_mcp_bridge_state()

    def set_mcp_bridge_server_enabled(self, server_id: str, *, enabled: bool) -> dict[str, object]:
        set_mcp_bridge_server_enabled(server_id, enabled, self.workspace_root)
        return self.get_mcp_bridge_state()

    def get_workbench_overview(self) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            collaboration_repository = CollaborationRepository(session)
            memory_repository = MemoryRepository(session)
            runtime_repository = RuntimeRepository(session)
            recent_tasks = task_repository.list_tasks(limit=6)
            recent_pull_requests = collaboration_repository.list_pull_requests(limit=6)
            recent_import_jobs = memory_repository.list_import_jobs(limit=4)
            recent_model_invocations = runtime_repository.list_model_invocations(limit=6)
            task_status_counts = self._status_counts(session, TaskORM, TaskORM.status)
            pull_request_status_counts = self._status_counts(session, PullRequestORM, PullRequestORM.status)
            import_status_counts = self._status_counts(session, ImportJobORM, ImportJobORM.status)
            outbox_status_counts = self._status_counts(session, OutboxRecordORM, OutboxRecordORM.publish_status)
            total_nodes = self._scalar_count(session, NodeORM, NodeORM.node_type != "root")
            total_branches = self._scalar_count(session, MemoryBranchORM)
            total_retrievals = self._scalar_count(session, RetrievalRequestORM)
            total_shared_spaces = self._scalar_count(session, SpaceORM, SpaceORM.space_type == "shared")
            total_space_mounts = self._scalar_count(session, SpaceMountORM)
            total_permission_tuples = self._scalar_count(session, PermissionTupleORM)
            total_restorable_snapshots = self._scalar_count(session, TaskSnapshotORM, TaskSnapshotORM.status == "restorable")
            llm_summary = self._llm_summary(session)

        module_snapshot = sync_module_catalog_snapshot(self.workspace_root)
        module_summary = {
            "total": len(module_snapshot.installs),
            "active": len([record for record in module_snapshot.installs if record.lifecycle_state == "active"]),
            "degraded": len([record for record in module_snapshot.installs if record.lifecycle_state == "degraded"]),
            "disabled": len([record for record in module_snapshot.installs if record.desired_state == "disabled"]),
        }
        observability = self.get_observability_summary(limit=12)
        evaluation_runs = self.list_evaluation_runs(limit=5)["evaluationRuns"]
        evaluation_suites = self.list_evaluation_suites()["evaluationSuites"]

        return {
            "generatedAt": utc_now().isoformat(),
            "health": self.health_report(),
            "cards": {
                "tasks": sum(task_status_counts.values()),
                "nodes": total_nodes,
                "branches": total_branches,
                "pullRequests": sum(pull_request_status_counts.values()),
                "imports": sum(import_status_counts.values()),
                "retrievals": total_retrievals,
                "outboxPending": outbox_status_counts.get("pending", 0),
                "evaluationRuns": len(evaluation_runs),
                "observabilityErrors": sum(item["errorCount"] for item in observability.get("serviceSummaries", [])),
                "modelInvocations": int(llm_summary["totalInvocations"]),
                "llmFallbacks": int(llm_summary["fallbackInvocations"]),
                "llmCostUsed": float(llm_summary["totalCostUsed"]),
                "sharedSpaces": total_shared_spaces,
                "spaceMounts": total_space_mounts,
                "permissionTuples": total_permission_tuples,
                "pausedTasks": task_status_counts.get("paused", 0),
                "restorableSnapshots": total_restorable_snapshots,
            },
            "moduleSummary": module_summary,
            "llmSummary": llm_summary,
            "taskStatusCounts": task_status_counts,
            "pullRequestStatusCounts": pull_request_status_counts,
            "importJobStatusCounts": import_status_counts,
            "outboxStatusCounts": outbox_status_counts,
            "recentTasks": [task.model_dump(by_alias=True, mode="json") for task in recent_tasks],
            "recentPullRequests": [record.model_dump(by_alias=True, mode="json") for record in recent_pull_requests],
            "recentImportJobs": [record.model_dump(by_alias=True, mode="json") for record in recent_import_jobs],
            "recentModelInvocations": [record.model_dump(by_alias=True, mode="json") for record in recent_model_invocations],
            "recentEvaluationRuns": evaluation_runs,
            "evaluationSuites": evaluation_suites,
            "observability": observability,
        }

    def list_spaces(
        self,
        *,
        project_id: str | None = None,
        space_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            spaces = CollaborationRepository(session).list_spaces(
                project_id=project_id,
                space_type=space_type,
                status=status,
                limit=limit,
            )
        return {"spaces": [space.model_dump(by_alias=True, mode="json") for space in spaces]}

    def create_space(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            space = CollaborationRepository(session).create_space(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": space.project_id,
                    "aggregateType": "space",
                    "aggregateId": space.id,
                    "eventType": "space.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/spaces/{space.id}"},
                }
            )
        return {
            "space": space.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_modules(self) -> dict[str, object]:
        snapshot = sync_module_catalog_snapshot(self.workspace_root)
        installs_by_module_id = {record.module_id: record for record in snapshot.installs}
        return {
            "source": "database-module-catalog",
            "generatedAt": snapshot.generated_at,
            "modules": [
                {
                    "moduleId": manifest.module_id,
                    "displayName": manifest.display_name,
                    "version": manifest.version,
                    "category": manifest.category,
                    "runtimeMode": manifest.runtime_mode,
                    "desiredState": installs_by_module_id[manifest.module_id].desired_state,
                    "lifecycleState": installs_by_module_id[manifest.module_id].lifecycle_state,
                    "hooks": manifest.hooks,
                    "publishes": manifest.publishes,
                    "subscribes": manifest.subscribes,
                    "requestedPermissions": manifest.requested_permissions,
                    "manifestPath": manifest.manifest_path,
                }
                for manifest in snapshot.manifests
            ],
        }

    def list_nodes(self, *, branch_id: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            nodes = NodeRepository(session).list_nodes(branch_id=branch_id, limit=limit)
        return {"nodes": [node.model_dump(by_alias=True, mode="json") for node in nodes]}

    def get_node(self, node_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            node = repository.get_node(node_id)
            if node is None:
                raise KeyError(node_id)
            versions = repository.list_versions(node_id)
            annotations = repository.list_source_annotations(owner_kind="node", owner_id=node_id, limit=500)
            edges = repository.list_edges(node_id=node_id, limit=500)
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "versions": [version.model_dump(by_alias=True, mode="json") for version in versions],
            "annotations": [annotation.model_dump(by_alias=True, mode="json") for annotation in annotations],
            "outgoingEdges": [edge.model_dump(by_alias=True, mode="json") for edge in edges if edge.from_node_id == node_id],
            "incomingEdges": [edge.model_dump(by_alias=True, mode="json") for edge in edges if edge.to_node_id == node_id],
        }

    def create_node(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node = NodeRepository(session).create_node(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": node.project_id,
                    "aggregateType": "node",
                    "aggregateId": node.id,
                    "eventType": "node.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node.id}"},
                }
            )
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def append_node_version(self, node_id: str, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            version = repository.append_version(node_id, payload)
            node = repository.get_node(node_id)
            if node is None:
                raise KeyError(node_id)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": node.project_id,
                    "aggregateType": "node-version",
                    "aggregateId": version.id,
                    "eventType": "node.version.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node_id}/versions/{version.id}"},
                }
            )
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "version": version.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def add_node_annotation(self, node_id: str, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            if repository.get_node(node_id) is None:
                raise KeyError(node_id)
            annotation = repository.add_source_annotation("node", node_id, payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": annotation.project_id,
                    "aggregateType": "source-annotation",
                    "aggregateId": annotation.id,
                    "eventType": "source.annotation.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node_id}/annotations/{annotation.id}"},
                }
            )
        return {
            "annotation": annotation.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_tasks(self, *, status: str | None = None, app_id: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            tasks = TaskRepository(session).list_tasks(status=status, app_id=app_id, limit=limit)
        return {"tasks": [task.model_dump(by_alias=True, mode="json") for task in tasks]}

    def start_task(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        return queue_runtime_task_execution(task_id, dict(payload or {}))

    def request_task_pause(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        return request_runtime_task_pause(task_id, dict(payload or {}))

    def resume_task(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        request = dict(payload or {})
        request["command"] = "resume"
        return queue_runtime_task_execution(task_id, request)

    def list_branches(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            branches = CollaborationRepository(session).list_branches(
                project_id=project_id,
                space_id=space_id,
                status=status,
                limit=limit,
            )
        return {"branches": [branch.model_dump(by_alias=True, mode="json") for branch in branches]}

    def create_branch(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            branch = CollaborationRepository(session).create_branch(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": branch.project_id,
                    "aggregateType": "branch",
                    "aggregateId": branch.id,
                    "eventType": "branch.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/branches/{branch.id}"},
                }
            )
        return {
            "branch": branch.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_space_mounts(
        self,
        *,
        project_id: str | None = None,
        host_space_id: str | None = None,
        mounted_space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            mounts = CollaborationRepository(session).list_space_mounts(
                project_id=project_id,
                host_space_id=host_space_id,
                mounted_space_id=mounted_space_id,
                status=status,
                limit=limit,
            )
        return {"spaceMounts": [mount.model_dump(by_alias=True, mode="json") for mount in mounts]}

    def create_space_mount(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            mount = CollaborationRepository(session).create_space_mount(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": mount.project_id,
                    "aggregateType": "space-mount",
                    "aggregateId": mount.id,
                    "eventType": "space.mount.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/space-mounts/{mount.id}"},
                }
            )
        return {
            "spaceMount": mount.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_permission_tuples(
        self,
        *,
        project_id: str | None = None,
        subject: str | None = None,
        relation: str | None = None,
        resource: str | None = None,
        effect: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            tuples = CollaborationRepository(session).list_permission_tuples(
                project_id=project_id,
                subject=subject,
                relation=relation,
                resource=resource,
                effect=effect,
                limit=limit,
            )
        return {"permissionTuples": [item.model_dump(by_alias=True, mode="json") for item in tuples]}

    def create_permission_tuple(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            permission_tuple = CollaborationRepository(session).create_permission_tuple(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": permission_tuple.project_id,
                    "aggregateType": "permission-tuple",
                    "aggregateId": permission_tuple.id,
                    "eventType": "permission.tuple.created",
                    "payloadRef": {
                        "type": "package-entry",
                        "locator": f"core-api/collaboration/permission-tuples/{permission_tuple.id}",
                    },
                }
            )
        return {
            "permissionTuple": permission_tuple.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_pull_requests(
        self,
        *,
        project_id: str | None = None,
        source_branch_id: str | None = None,
        target_branch_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            pull_requests = CollaborationRepository(session).list_pull_requests(
                project_id=project_id,
                source_branch_id=source_branch_id,
                target_branch_id=target_branch_id,
                status=status,
                limit=limit,
            )
        return {"pullRequests": [record.model_dump(by_alias=True, mode="json") for record in pull_requests]}

    def get_pull_request(self, pr_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            collaboration_repository = CollaborationRepository(session)
            pull_request = collaboration_repository.get_pull_request(pr_id)
            if pull_request is None:
                raise KeyError(pr_id)
            review_comments = collaboration_repository.list_review_comments(pr_id)
        return {
            "pullRequest": pull_request.model_dump(by_alias=True, mode="json"),
            "reviewComments": [comment.model_dump(by_alias=True, mode="json") for comment in review_comments],
        }

    def get_task(self, task_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            runtime_repository = RuntimeRepository(session)
            task = task_repository.get_task(task_id)
            if task is None:
                raise KeyError(task_id)
            runs = task_repository.list_agent_runs(task_id)
            snapshots = task_repository.list_snapshots(task_id)
            decisions = runtime_repository.list_model_route_decisions(task_id=task_id)
            invocations = runtime_repository.list_model_invocations(task_id=task_id, limit=50)
        return {
            "task": task.model_dump(by_alias=True, mode="json"),
            "agentRuns": [run.model_dump(by_alias=True, mode="json") for run in runs],
            "snapshots": [snapshot.model_dump(by_alias=True, mode="json") for snapshot in snapshots],
            "runtimeControl": self._task_runtime_control_summary(task, snapshots),
            "routeDecisions": [decision.model_dump(by_alias=True, mode="json") for decision in decisions],
            "modelInvocations": [invocation.model_dump(by_alias=True, mode="json") for invocation in invocations],
        }

    def create_task(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task = TaskRepository(session).create_task(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": task.project_id,
                    "aggregateType": "task",
                    "aggregateId": task.id,
                    "eventType": "task.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/tasks/{task.id}"},
                }
            )
        return {
            "task": task.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def launch_subagent(self, parent_task_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return launch_subagent_task(parent_task_id, payload)

    def create_pull_request(self, payload: dict[str, Any]) -> dict[str, object]:
        return create_collaboration_pull_request(payload)

    def review_pull_request(self, pr_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return review_collaboration_pull_request(pr_id, payload)

    def create_agent_run(self, task_id: str, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            run = TaskRepository(session).create_agent_run(task_id, payload)
            event = OutboxRepository(session).record_event(
                {
                    "aggregateType": "agent-run",
                    "aggregateId": run.id,
                    "eventType": "agent.run.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/tasks/{task_id}/runs/{run.id}"},
                }
            )
        return {
            "run": run.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_task_snapshots(self, task_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            snapshots = TaskRepository(session).list_snapshots(task_id)
        return {"snapshots": [snapshot.model_dump(by_alias=True, mode="json") for snapshot in snapshots]}

    def list_route_decisions(self, *, task_id: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            decisions = RuntimeRepository(session).list_model_route_decisions(task_id=task_id, limit=limit)
        return {"routeDecisions": [decision.model_dump(by_alias=True, mode="json") for decision in decisions]}

    def list_model_invocations(
        self,
        *,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        app_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            invocations = RuntimeRepository(session).list_model_invocations(
                task_id=task_id,
                agent_run_id=agent_run_id,
                app_id=app_id,
                status=status,
                limit=limit,
            )
        return {"modelInvocations": [invocation.model_dump(by_alias=True, mode="json") for invocation in invocations]}

    def create_route_decision(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            decision = RuntimeRepository(session).create_model_route_decision(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": payload.get("projectId"),
                    "aggregateType": "model-route-decision",
                    "aggregateId": decision.id,
                    "eventType": "runtime.model-route.selected",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/runtime/route-decisions/{decision.id}"},
                }
            )
        return {
            "routeDecision": decision.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_outbox(self, *, publish_status: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            events = OutboxRepository(session).list_events(publish_status=publish_status, limit=limit)
        return {"events": [event.model_dump(by_alias=True, mode="json") for event in events]}

    def list_import_jobs(self, *, status: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            jobs = MemoryRepository(session).list_import_jobs(status=status, limit=limit)
        return {"importJobs": [job.model_dump(by_alias=True, mode="json") for job in jobs]}

    def get_import_job(self, import_job_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            node_repository = NodeRepository(session)
            import_job = memory_repository.get_import_job(import_job_id)
            if import_job is None:
                raise KeyError(import_job_id)
            fragments = memory_repository.list_import_fragments(import_job_id)
            tree_plans = memory_repository.list_tree_plans(import_job_id)
            latest_tree_plan = tree_plans[0] if tree_plans else None
            node_ids = [str(payload.get("id")) for payload in (latest_tree_plan.candidate_node_payloads if latest_tree_plan else [])]
            edge_ids = {str(payload.get("id")) for payload in (latest_tree_plan.candidate_edge_payloads if latest_tree_plan else [])}
            annotation_ids = {str(payload.get("id")) for payload in (latest_tree_plan.candidate_source_annotations if latest_tree_plan else [])}
            materialized_nodes = [
                record.model_dump(by_alias=True, mode="json")
                for node_id in node_ids
                for record in [node_repository.get_node(node_id)]
                if record is not None
            ]
            materialized_edges = [
                record.model_dump(by_alias=True, mode="json")
                for record in node_repository.list_edges(branch_id=import_job.branch_id, limit=2000)
                if record.id in edge_ids
            ]
            materialized_annotations = [
                record.model_dump(by_alias=True, mode="json")
                for record in node_repository.list_source_annotations(branch_id=import_job.branch_id, limit=2000)
                if record.id in annotation_ids
            ]
        return {
            "importJob": import_job.model_dump(by_alias=True, mode="json"),
            "fragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
            "treePlans": [plan.model_dump(by_alias=True, mode="json") for plan in tree_plans],
            "materializedNodes": materialized_nodes,
            "materializedEdges": materialized_edges,
            "materializedSourceAnnotations": materialized_annotations,
        }

    def create_import_job(self, payload: dict[str, Any]) -> dict[str, object]:
        process_immediately = bool(payload.get("processImmediately", False))
        ordered_fragments = payload.get("orderedFragments") if isinstance(payload.get("orderedFragments"), list) else None
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.create_import_job(payload)
            if ordered_fragments:
                memory_repository.replace_import_fragments(import_job.id, ordered_fragments)
            outbox_record = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="import.accepted",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )
        if process_immediately:
            result = self.process_import_job(import_job.id, payload)
            result["acceptedOutboxRecord"] = outbox_record.model_dump(by_alias=True, mode="json")
            return result
        return {
            "importJob": import_job.model_dump(by_alias=True, mode="json"),
            "outboxRecord": outbox_record.model_dump(by_alias=True, mode="json"),
        }

    def process_import_job(self, import_job_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        request_payload = payload or {}
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.get_import_job(import_job_id)
            if import_job is None:
                raise KeyError(import_job_id)
            if import_job.status == "completed":
                return {"status": "completed", **self.get_import_job(import_job_id)}
            memory_repository.set_import_job_status(import_job_id, "preprocessing")
            existing_fragments = memory_repository.list_import_fragments(import_job_id)

        if isinstance(request_payload.get("orderedFragments"), list):
            preprocess_result = {
                "status": "ok",
                "orderedFragments": request_payload["orderedFragments"],
            }
        elif request_payload.get("sourceText") is not None or isinstance(request_payload.get("sourceTexts"), list):
            preprocess_result = self._call_module_hook(
                "text-memory",
                HookNames.MEMORY_INGEST_PREPROCESS,
                {
                    "importJob": import_job.model_dump(by_alias=True, mode="json"),
                    "importPolicy": import_job.import_policy.model_dump(by_alias=True),
                    "sourceText": request_payload.get("sourceText"),
                    "sourceTexts": request_payload.get("sourceTexts"),
                    "rawRef": request_payload.get("rawRef"),
                },
            )
        elif existing_fragments:
            preprocess_result = {
                "status": "ok",
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in existing_fragments],
            }
        else:
            raise ValueError("Import processing requires sourceText, sourceTexts, orderedFragments, or previously persisted fragments.")

        if str(preprocess_result.get("status") or "ok").lower() == "error":
            with self.runtime.session_scope() as session:
                WorkspaceBootstrapRepository(session).ensure_default_workspace()
                import_job = MemoryRepository(session).set_import_job_status(
                    import_job_id,
                    "failed",
                    failure_reason=str(preprocess_result.get("summary") or "Import preprocessing failed."),
                )
            return {
                "status": "failed",
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
            }

        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.set_import_job_status(import_job_id, "planning")
            fragments = memory_repository.replace_import_fragments(import_job_id, list(preprocess_result.get("orderedFragments") or []))
            segmented_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="import.segmented",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )

        envelope = EventEnvelope(
            eventType="import.accepted",
            eventVersion=1,
            eventId=new_id("evt", "import.accepted", import_job.id),
            occurredAt=utc_now(),
            source="core-api",
            actor=ActorRef(type="system", id="core-api"),
            projectId=import_job.project_id,
            spaceId="space_default",
            branchId=import_job.branch_id,
            correlationId=import_job.id,
            schemaRef="yggdrasil://events/import.accepted/v1",
            payload={
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
                "importPolicy": import_job.import_policy.model_dump(by_alias=True),
            },
        )
        handling_result = self._dispatch_module_event("text-memory", envelope)
        plan_emissions = [event for event in handling_result.emitted_events if event.event_type == "memory.tree.plan.proposed"]
        if not plan_emissions:
            raise RuntimeError("text-memory did not emit memory.tree.plan.proposed.")
        plan_payload = dict(plan_emissions[0].payload)
        plan_payload["importJobId"] = import_job.id
        plan_payload["status"] = "proposed"
        plan_payload["candidateNodePayloads"] = list(plan_payload.pop("candidateNodes", []))
        plan_payload["candidateEdgePayloads"] = list(plan_payload.pop("candidateEdges", []))
        plan_payload["candidateSourceAnnotations"] = list(plan_payload.pop("candidateSourceAnnotations", []))
        plan_payload["proposedBy"] = {"type": "module", "id": "text-memory"}
        confidence = plan_payload.pop("confidence", None)
        if confidence is not None:
            plan_payload["rationale"] = f"{plan_payload.get('rationale', 'Generated tree plan.')} Confidence={confidence}."

        validation_result = self._call_module_hook(
            "text-memory",
            HookNames.MEMORY_WRITE_VALIDATE,
            {
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
                "candidateNodes": plan_payload["candidateNodePayloads"],
                "candidateEdges": plan_payload["candidateEdgePayloads"],
            },
        )
        if str(validation_result.get("status") or "ok").lower() == "error":
            with self.runtime.session_scope() as session:
                WorkspaceBootstrapRepository(session).ensure_default_workspace()
                memory_repository = MemoryRepository(session)
                import_job = memory_repository.set_import_job_status(
                    import_job_id,
                    "failed",
                    failure_reason=str(validation_result.get("summary") or "Memory write validation failed."),
                )
            return {
                "status": "failed",
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "validation": validation_result,
            }

        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.set_import_job_status(import_job_id, "materializing")
            tree_plan = memory_repository.upsert_tree_plan(plan_payload)
            plan_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="tree-plan",
                aggregate_id=tree_plan.id,
                event_type="memory.tree.plan.proposed",
                locator=f"core-api/memory/import-jobs/{import_job.id}/tree-plans/{tree_plan.id}",
            )
            memory_repository.set_tree_plan_status(tree_plan.id, "accepted")
            materialized = self._materialize_tree_plan(session, import_job=import_job, tree_plan=tree_plan)
            memory_repository.set_tree_plan_status(tree_plan.id, "materialized")
            import_job = memory_repository.set_import_job_status(import_job_id, "completed")
            materialized_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="memory.tree.materialized",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )

        details = self.get_import_job(import_job_id)
        return {
            "status": "completed",
            **details,
            "validation": validation_result,
            "segmentedOutboxRecord": segmented_event.model_dump(by_alias=True, mode="json"),
            "treePlanOutboxRecord": plan_event.model_dump(by_alias=True, mode="json"),
            "materializedOutboxRecord": materialized_event.model_dump(by_alias=True, mode="json"),
            "materialized": materialized,
        }

    def create_retrieval(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            node_repository = NodeRepository(session)
            retrieval_request = memory_repository.create_retrieval_request(payload)
            nodes = node_repository.list_nodes(branch_id=retrieval_request.branch_id, limit=2000)
            edges = node_repository.list_edges(branch_id=retrieval_request.branch_id, limit=4000)
            annotations = node_repository.list_source_annotations(branch_id=retrieval_request.branch_id, limit=4000)
        result = self._call_module_hook(
            "text-memory",
            HookNames.MEMORY_RETRIEVE_EXPAND,
            {
                "retrievalRequest": retrieval_request.model_dump(by_alias=True, mode="json"),
                "nodes": [node.model_dump(by_alias=True, mode="json") for node in nodes],
                "edges": [edge.model_dump(by_alias=True, mode="json") for edge in edges],
                "sourceAnnotations": [annotation.model_dump(by_alias=True, mode="json") for annotation in annotations],
            },
        )
        bundle = RetrievalBundle.model_validate(result)
        return {
            "retrievalRequest": retrieval_request.model_dump(by_alias=True, mode="json"),
            "retrievalBundle": bundle.model_dump(by_alias=True, mode="json"),
        }


def get_workspace_service() -> WorkspaceService:
    ensure_workspace_bootstrap()
    return WorkspaceService()