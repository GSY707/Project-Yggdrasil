from __future__ import annotations

from pathlib import Path
from typing import Any

import sqlalchemy as sa

from yggdrasil_sdk import (
    ActorRef,
    CollaborationRepository,
    EvaluationRepository,
    EventEnvelope,
    ensure_evaluation_suites,
    HookNames,
    list_evaluation_suite_definitions,
    MemoryRepository,
    NodeRepository,
    OutboxRepository,
    RedisCoordinator,
    RetrievalBundle,
    RuntimeRepository,
    run_evaluation_suite,
    summarize_observability,
    TaskRepository,
    ensure_workspace_bootstrap,
    get_persistence_runtime,
    load_in_process_plugin,
    new_id,
    sync_module_catalog_snapshot,
    utc_now,
)
from yggdrasil_sdk.collaboration_runtime import create_pull_request as create_collaboration_pull_request
from yggdrasil_sdk.collaboration_runtime import launch_subagent_task, review_pull_request as review_collaboration_pull_request
from yggdrasil_sdk.persistence.orm import ImportJobORM, MemoryBranchORM, ModelInvocationORM, NodeORM, OutboxRecordORM, PullRequestORM, RetrievalRequestORM, TaskORM
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
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

    def _load_metrics_payload(self, locator: str | None) -> dict[str, Any] | None:
        if not locator:
            return None
        payload = read_json(Path(locator), None)
        return payload if isinstance(payload, dict) else None

    def _load_module(self, module_id: str):
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

    def _dispatch_module_event(self, module_id: str, envelope: EventEnvelope):
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

    def list_tasks(self, *, status: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            tasks = TaskRepository(session).list_tasks(status=status, limit=limit)
        return {"tasks": [task.model_dump(by_alias=True, mode="json") for task in tasks]}

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
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            invocations = RuntimeRepository(session).list_model_invocations(
                task_id=task_id,
                agent_run_id=agent_run_id,
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