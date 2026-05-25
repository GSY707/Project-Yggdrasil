from ._base import *  # noqa: F403,F401
from yggdrasil_sdk.llm_work_analysis import analyze_llm_work_run, load_persisted_llm_work_analysis

class RuntimeServiceMixin:
    def health_report(self) -> dict[str, object]:
        return {
            "status": "ok",
            "service": "core-api",
            "database": self.runtime.ping_database(),
            "redis": self.coordinator.ping(),
        }

    def analyze_llm_work(self, payload: dict[str, Any] | None = None) -> dict[str, object]:
        request = dict(payload or {})
        return analyze_llm_work_run(
            task_id=str(request.get("taskId") or "").strip() or None,
            run_id=str(request.get("runId") or "").strip() or None,
            invocation_id=str(request.get("invocationId") or "").strip() or None,
            granularities=request.get("granularity"),
            persist=bool(request.get("persist", True)),
            workspace_root=self.workspace_root,
        )

    def get_llm_work_analysis(self, analysis_id: str, *, granularity: str | None = None) -> dict[str, object]:
        return load_persisted_llm_work_analysis(
            analysis_id,
            granularities=granularity,
            workspace_root=self.workspace_root,
        )

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

    def _task_runtime_control_summary(self, task, snapshots: list[Any], runs: list[Any]) -> dict[str, object]:
        latest_snapshot = snapshots[0] if snapshots else None
        latest_restorable_snapshot = next((snapshot for snapshot in snapshots if snapshot.status == "restorable"), None)
        latest_run = runs[0] if runs else None
        latest_takeover_protocol = (
            load_persisted_task_takeover_protocol(task.id, latest_run.id)
            if latest_run is not None
            else None
        )
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
            "canApprove": bool(task.status == "awaiting-approval"),
            "canRequestRevision": bool(task.status == "awaiting-approval"),
            "recommendedResumeToken": latest_restorable_snapshot.resume_token if latest_restorable_snapshot is not None else None,
            "recommendedResumeMessage": (
                latest_restorable_snapshot.resume_message
                if latest_restorable_snapshot is not None
                else task.resume_message
            ),
            "recommendedRevisionNodeId": (
                latest_takeover_protocol.work_tree.current_node_id
                if latest_takeover_protocol is not None and latest_takeover_protocol.work_tree is not None
                else None
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


