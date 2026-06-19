from ._common import *
from .platform_core import WorkspaceBootstrapRepository
from ..write_queue import run_serialized_write
from hashlib import sha256


def _hash_resume_token(value: str | None) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    return sha256(token.encode("utf-8")).hexdigest()


def _ensure_task_workspace(
    session: Session,
    *,
    project_id: str,
    space_id: str,
    branch_id: str,
    branch_name: str | None = None,
) -> dict[str, str]:
    bootstrap = WorkspaceBootstrapRepository(session)
    if project_id == DEFAULT_PROJECT_ID and space_id == DEFAULT_SPACE_ID:
        bootstrap.ensure_default_workspace()

    project = session.get(ProjectORM, project_id)
    if project is None:
        raise KeyError(f"Project {project_id} not found.")

    space = session.get(SpaceORM, space_id)
    if space is None:
        raise KeyError(f"Space {space_id} not found.")
    if space.project_id != project_id:
        raise ValueError(f"Space {space_id} does not belong to project {project_id}.")

    branch = session.get(MemoryBranchORM, branch_id)
    if branch is not None:
        if branch.project_id != project_id:
            raise ValueError(f"Branch {branch_id} does not belong to project {project_id}.")
        if branch.space_id != space_id:
            raise ValueError(f"Branch {branch_id} does not belong to space {space_id}.")
        if branch.status == "deleted":
            raise ValueError(f"Branch {branch_id} is deleted and cannot host a task.")

    return bootstrap.ensure_branch_workspace(
        branch_id=branch_id,
        project_id=project_id,
        space_id=space_id,
        branch_name=branch_name,
    )

class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_tasks(self, *, status: str | None = None, app_id: str | None = None, limit: int = 100) -> list[TaskRecord]:
        statement = sa.select(TaskORM).order_by(TaskORM.created_at.desc()).limit(limit)
        if status:
            statement = statement.where(TaskORM.status == status)
        if app_id:
            statement = statement.where(TaskORM.app_id == app_id)
        return [_task_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_task(self, task_id: str) -> TaskRecord | None:
        model = self.session.get(TaskORM, task_id)
        return _task_record(model) if model else None

    def update_task(self, task_id: str, payload: dict[str, Any]) -> TaskRecord:
        def _update() -> TaskRecord:
            task = self.session.get(TaskORM, task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found.")

            now = payload.get("updatedAt") or utc_now()

            if "status" in payload:
                task.status = str(payload["status"])
                if task.status in {"running", "restarting"}:
                    task.started_at = payload.get("startedAt") or task.started_at or now
                if task.status in {"completed", "failed", "cancelled"}:
                    task.ended_at = payload.get("endedAt") or now

            if "currentFocus" in payload:
                task.current_focus = str(payload["currentFocus"]) if payload["currentFocus"] is not None else None
            if "currentObjective" in payload:
                task.current_objective = (
                    str(payload["currentObjective"]) if payload["currentObjective"] is not None else None
                )
            if "resumeMessage" in payload:
                task.resume_message = str(payload["resumeMessage"]) if payload["resumeMessage"] is not None else None
            if "restartMessage" in payload:
                task.restart_message = str(payload["restartMessage"]) if payload["restartMessage"] is not None else None
            if "appId" in payload:
                task.app_id = str(payload["appId"]) if payload["appId"] is not None else DEFAULT_APP_ID
            if "executionRootNodeId" in payload:
                task.execution_root_node_id = (
                    str(payload["executionRootNodeId"]) if payload["executionRootNodeId"] is not None else None
                )
            if "activeSnapshotId" in payload:
                task.active_snapshot_id = str(payload["activeSnapshotId"]) if payload["activeSnapshotId"] is not None else None
            if "activeResumeAttemptId" in payload:
                task.active_resume_attempt_id = str(payload["activeResumeAttemptId"]) if payload["activeResumeAttemptId"] is not None else None
            if "resumeBlockedReason" in payload:
                task.resume_blocked_reason = str(payload["resumeBlockedReason"]) if payload["resumeBlockedReason"] is not None else None
            if "pendingControlIntent" in payload:
                task.pending_control_intent = str(payload["pendingControlIntent"]) if payload["pendingControlIntent"] is not None else None
            if "windowIndex" in payload:
                task.window_index = max(int(payload["windowIndex"]), 1)
            if "restartCount" in payload:
                task.restart_count = max(int(payload["restartCount"]), 0)
            if "cumulativeWindowSpanTokens" in payload:
                task.cumulative_window_span_tokens = max(int(payload["cumulativeWindowSpanTokens"]), 0)
            if "carryForwardLossCount" in payload:
                task.carry_forward_loss_count = max(int(payload["carryForwardLossCount"]), 0)
            if "pauseRequested" in payload:
                task.pause_requested = bool(payload["pauseRequested"])
            if "lastSafeStopAt" in payload:
                task.last_safe_stop_at = payload["lastSafeStopAt"]
            if "budget" in payload or "budgetState" in payload:
                budget = BudgetState.model_validate(payload.get("budget") or payload.get("budgetState") or {})
                task.budget = budget.model_dump(by_alias=True, mode="json")

            task.updated_at = now
            self.session.flush()
            return _task_record(task)

        return run_serialized_write(f"task:{task_id}", _update)

    def get_agent_run(self, agent_run_id: str) -> AgentRunRecord | None:
        model = self.session.get(AgentRunORM, agent_run_id)
        return _agent_run_record(model) if model else None

    def list_agent_runs(self, task_id: str, *, limit: int = 100) -> list[AgentRunRecord]:
        statement = (
            sa.select(AgentRunORM)
            .where(AgentRunORM.task_id == task_id)
            .order_by(AgentRunORM.started_at.desc(), AgentRunORM.ended_at.desc(), AgentRunORM.id.desc())
            .limit(limit)
        )
        return [_agent_run_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_latest_agent_run(self, task_id: str, *, statuses: set[str] | None = None) -> AgentRunRecord | None:
        statement = (
            sa.select(AgentRunORM)
            .where(AgentRunORM.task_id == task_id)
            .order_by(AgentRunORM.started_at.desc(), AgentRunORM.ended_at.desc(), AgentRunORM.id.desc())
            .limit(20)
        )
        models = self.session.execute(statement).scalars().all()
        for model in models:
            if statuses is None or model.status in statuses:
                return _agent_run_record(model)
        return None

    def update_agent_run(self, agent_run_id: str, payload: dict[str, Any]) -> AgentRunRecord:
        run = self.session.get(AgentRunORM, agent_run_id)
        if run is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")

        if "parentRunId" in payload:
            run.parent_run_id = str(payload["parentRunId"]) if payload["parentRunId"] is not None else None
        if "selectedModel" in payload:
            run.selected_model = str(payload["selectedModel"])
        if "selectedProvider" in payload:
            run.selected_provider = str(payload["selectedProvider"]) if payload["selectedProvider"] is not None else None
        if "routeDecisionId" in payload:
            run.route_decision_id = str(payload["routeDecisionId"]) if payload["routeDecisionId"] is not None else None
        if "status" in payload:
            run.status = str(payload["status"])
            if run.status in {"completed", "failed", "aborted"}:
                run.ended_at = payload.get("endedAt") or utc_now()
        if "nextObjective" in payload:
            run.next_objective = str(payload["nextObjective"]) if payload["nextObjective"] is not None else None
        if "windowIndex" in payload:
            run.window_index = max(int(payload["windowIndex"]), 1)
        if "restartCount" in payload:
            run.restart_count = max(int(payload["restartCount"]), 0)
        if "cumulativeWindowSpanTokens" in payload:
            run.cumulative_window_span_tokens = max(int(payload["cumulativeWindowSpanTokens"]), 0)
        if "inputTokensUsed" in payload:
            run.input_tokens_used = int(payload["inputTokensUsed"])
        if "outputTokensUsed" in payload:
            run.output_tokens_used = int(payload["outputTokensUsed"])
        if "costUsed" in payload:
            run.cost_used = float(payload["costUsed"])

        self.session.flush()
        return _agent_run_record(run)

    def create_task(self, payload: dict[str, Any]) -> TaskRecord:
        now = utc_now()
        budget = BudgetState.model_validate(payload.get("budget") or payload.get("budgetState") or {})
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        space_id = str(payload.get("spaceId") or DEFAULT_SPACE_ID)
        branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)
        app_id = str(payload.get("appId") or DEFAULT_APP_ID)
        workspace_roots = _ensure_task_workspace(
            self.session,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            branch_name=str(payload.get("branchName")) if payload.get("branchName") is not None else None,
        )
        task = TaskORM(
            id=str(payload.get("id") or new_id("task", payload.get("title") or now.isoformat())),
            app_id=app_id,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            title=str(payload.get("title") or "Untitled Task"),
            goal=str(payload.get("goal") or payload.get("objective") or ""),
            status=str(payload.get("status") or "draft"),
            current_focus=str(payload.get("currentFocus")) if payload.get("currentFocus") is not None else None,
            current_objective=str(payload.get("currentObjective")) if payload.get("currentObjective") is not None else None,
            resume_message=str(payload.get("resumeMessage")) if payload.get("resumeMessage") is not None else None,
            restart_message=str(payload.get("restartMessage")) if payload.get("restartMessage") is not None else None,
            owner_profile_id=str(payload.get("ownerProfileId") or DEFAULT_OWNER_PROFILE_ID),
            execution_root_node_id=str(payload.get("executionRootNodeId") or workspace_roots.get("execution") or new_id("node", project_id, branch_id, "execution", stable=True)),
            active_snapshot_id=None,
            active_resume_attempt_id=None,
            resume_blocked_reason=None,
            pending_control_intent=None,
            window_index=max(int(payload.get("windowIndex", 1)), 1),
            restart_count=max(int(payload.get("restartCount", 0)), 0),
            cumulative_window_span_tokens=max(int(payload.get("cumulativeWindowSpanTokens", 0)), 0),
            carry_forward_loss_count=max(int(payload.get("carryForwardLossCount", 0)), 0),
            budget=budget.model_dump(by_alias=True, mode="json"),
            pause_requested=bool(payload.get("pauseRequested", False)),
            last_safe_stop_at=None,
            started_at=None,
            ended_at=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        self.session.flush()
        return _task_record(task)

    def create_agent_run(self, task_id: str, payload: dict[str, Any]) -> AgentRunRecord:
        task = self.session.get(TaskORM, task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        now = utc_now()
        app_id = str(payload.get("appId") or task.app_id or DEFAULT_APP_ID)
        if task.app_id and app_id != task.app_id:
            raise ValueError(f"Agent run appId {app_id} does not match task {task_id} appId {task.app_id}.")
        run = AgentRunORM(
            id=str(payload.get("id") or new_id("run", task_id, now.isoformat())),
            app_id=app_id,
            task_id=task_id,
            project_id=task.project_id,
            branch_id=task.branch_id,
            parent_run_id=str(payload.get("parentRunId")) if payload.get("parentRunId") is not None else None,
            run_type=str(payload.get("runType") or "main"),
            selected_model=str(payload.get("selectedModel") or "gpt-5.4"),
            selected_provider=str(payload.get("selectedProvider")) if payload.get("selectedProvider") is not None else None,
            route_decision_id=str(payload.get("routeDecisionId")) if payload.get("routeDecisionId") is not None else None,
            status=str(payload.get("status") or "initializing"),
            next_objective=str(payload.get("nextObjective")) if payload.get("nextObjective") is not None else None,
            window_index=max(int(payload.get("windowIndex", 1)), 1),
            restart_count=max(int(payload.get("restartCount", 0)), 0),
            cumulative_window_span_tokens=max(int(payload.get("cumulativeWindowSpanTokens", 0)), 0),
            input_tokens_used=int(payload.get("inputTokensUsed", 0)),
            output_tokens_used=int(payload.get("outputTokensUsed", 0)),
            cost_used=float(payload.get("costUsed", 0.0)),
            started_at=now,
            ended_at=None,
        )
        self.session.add(run)
        if task.status in {"draft", "queued"} and run.status in {"initializing", "mounting", "running"}:
            task.status = "running"
            task.started_at = task.started_at or now
            task.updated_at = now
        self.session.flush()
        return _agent_run_record(run)

    def create_snapshot(self, summary: TaskSnapshotSummary) -> TaskSnapshotSummary:
        def _create() -> TaskSnapshotSummary:
            task = self.session.get(TaskORM, summary.task_id)
            if task is None:
                raise KeyError(f"Task {summary.task_id} not found.")
            run = self.session.get(AgentRunORM, summary.agent_run_id) if summary.agent_run_id is not None else None
            if summary.agent_run_id is not None and run is None:
                raise KeyError(f"Agent run {summary.agent_run_id} not found.")
            if summary.app_id != task.app_id or (run is not None and summary.app_id != run.app_id):
                raise ValueError(
                    f"Snapshot appId {summary.app_id} does not match task/run app ids {task.app_id}/{run.app_id if run is not None else None}."
                )
            snapshot = TaskSnapshotORM(
                id=summary.id,
                app_id=summary.app_id,
                task_id=summary.task_id,
                agent_run_id=summary.agent_run_id,
                project_id=summary.project_id,
                branch_id=summary.branch_id,
                snapshot_type=summary.snapshot_type,
                status=summary.status,
                retention_class=summary.retention_class,
                schema_version=summary.schema_version,
                runtime_contract_version=summary.runtime_contract_version,
                storage_manifest_ref=summary.storage_manifest_ref.model_dump(mode="json") if summary.storage_manifest_ref else None,
                manifest_checksum=summary.manifest_checksum,
                resume_token_hash=summary.resume_token_hash or _hash_resume_token(summary.resume_token),
                resume_token=None,
                context_ref=summary.context_ref.model_dump(mode="json"),
                root_mount_ref=summary.root_mount_ref.model_dump(mode="json"),
                pending_writes=[reference.model_dump(mode="json") for reference in summary.pending_writes],
                pending_actions=list(summary.pending_actions),
                resume_message=summary.resume_message,
                safe_stop_reason=summary.safe_stop_reason,
                blocker_code=summary.blocker_code,
                blocker_message=summary.blocker_message,
                saved_label=summary.saved_label,
                saved_by_user_id=summary.saved_by_user_id,
                expires_at=summary.expires_at,
                created_at=summary.created_at,
                verified_at=summary.verified_at,
                leased_until=summary.leased_until,
                consumed_at=None,
                superseded_by_snapshot_id=summary.superseded_by_snapshot_id,
                safe_to_pause=summary.safe_to_pause,
                current_node_id=summary.current_node_id,
                working_node_annotation=summary.working_node_annotation,
                pc_memo=summary.pc_memo,
                top_frame_id=summary.top_frame_id,
                stack_digest=summary.stack_digest,
                blockers=list(summary.blockers),
            )
            self.session.add(snapshot)
            if summary.retention_class in {"active-paused", "latest-auto"}:
                task.active_snapshot_id = summary.id
                if summary.safe_to_pause:
                    task.last_safe_stop_at = summary.created_at
                task.updated_at = summary.created_at
            self.session.flush()
            return _task_snapshot_record(snapshot)

        return run_serialized_write(f"task-snapshot:{summary.task_id}", _create)

    def get_snapshot(self, snapshot_id: str) -> TaskSnapshotSummary | None:
        model = self.session.get(TaskSnapshotORM, snapshot_id)
        return _task_snapshot_record(model) if model else None

    def get_snapshot_by_resume_token(self, resume_token: str) -> TaskSnapshotSummary | None:
        token_hash = _hash_resume_token(resume_token)
        statement = sa.select(TaskSnapshotORM).where(
            sa.or_(TaskSnapshotORM.resume_token_hash == token_hash, TaskSnapshotORM.resume_token == resume_token)
        )
        model = self.session.execute(statement).scalar_one_or_none()
        return _task_snapshot_record(model) if model else None

    def update_snapshot(
        self,
        snapshot_id: str,
        *,
        status: str | None = None,
        consumed_at: datetime | None = None,
        blockers: list[str] | None = None,
        retention_class: str | None = None,
        blocker_code: str | None = None,
        blocker_message: str | None = None,
        saved_label: str | None = None,
        saved_by_user_id: str | None = None,
        expires_at: datetime | None = None,
        leased_until: datetime | None = None,
        manifest_checksum: str | None = None,
        storage_manifest_ref: ExternalRef | None = None,
        superseded_by_snapshot_id: str | None = None,
    ) -> TaskSnapshotSummary:
        snapshot = self.session.get(TaskSnapshotORM, snapshot_id)
        if snapshot is None:
            raise KeyError(f"Snapshot {snapshot_id} not found.")
        if status is not None:
            snapshot.status = status
        if retention_class is not None:
            snapshot.retention_class = retention_class
        if consumed_at is not None:
            snapshot.consumed_at = consumed_at
        if blockers is not None:
            snapshot.blockers = list(blockers)
        if blocker_code is not None:
            snapshot.blocker_code = blocker_code
        if blocker_message is not None:
            snapshot.blocker_message = blocker_message
        if saved_label is not None:
            snapshot.saved_label = saved_label
        if saved_by_user_id is not None:
            snapshot.saved_by_user_id = saved_by_user_id
        if expires_at is not None:
            snapshot.expires_at = expires_at
        if leased_until is not None:
            snapshot.leased_until = leased_until
        if manifest_checksum is not None:
            snapshot.manifest_checksum = manifest_checksum
        if storage_manifest_ref is not None:
            snapshot.storage_manifest_ref = storage_manifest_ref.model_dump(mode="json")
        if superseded_by_snapshot_id is not None:
            snapshot.superseded_by_snapshot_id = superseded_by_snapshot_id
        self.session.flush()
        return _task_snapshot_record(snapshot)

    def supersede_snapshots(self, task_id: str, *, keep_snapshot_id: str | None = None) -> int:
        def _supersede() -> int:
            statement = sa.select(TaskSnapshotORM).where(
                TaskSnapshotORM.task_id == task_id,
                TaskSnapshotORM.status.in_(["created", "flushed", "restorable"]),
            )
            updated = 0
            for snapshot in self.session.execute(statement).scalars().all():
                if keep_snapshot_id is not None and snapshot.id == keep_snapshot_id:
                    continue
                if snapshot.retention_class == "user-saved":
                    continue
                snapshot.status = "superseded"
                updated += 1
            self.session.flush()
            return updated

        return run_serialized_write(f"task-snapshot:{task_id}", _supersede)

    def list_snapshots(self, task_id: str) -> list[TaskSnapshotSummary]:
        statement = sa.select(TaskSnapshotORM).where(TaskSnapshotORM.task_id == task_id).order_by(TaskSnapshotORM.created_at.desc())
        return [_task_snapshot_record(model) for model in self.session.execute(statement).scalars().all()]

    def create_resume_attempt(self, task_id: str, snapshot_id: str, payload: dict[str, Any] | None = None) -> TaskResumeAttemptRecord:
        payload = payload or {}
        now = utc_now()
        existing = self.session.execute(
            sa.select(TaskResumeAttemptORM).where(
                TaskResumeAttemptORM.task_id == task_id,
                TaskResumeAttemptORM.status.in_(["queued", "leased", "restoring", "running", "blocked"]),
            ).order_by(TaskResumeAttemptORM.created_at.desc())
        ).scalar_one_or_none()
        if existing is not None:
            return _task_resume_attempt_record(existing)
        attempt = TaskResumeAttemptORM(
            id=str(payload.get("id") or new_id("resume-attempt", task_id, snapshot_id, now.isoformat())),
            task_id=task_id,
            snapshot_id=snapshot_id,
            requested_by=dict(payload.get("requestedBy") or {"type": "user", "id": "operator"}),
            status=str(payload.get("status") or "queued"),
            lease_owner=None,
            lease_until=None,
            blocker_code=None,
            blocker_message=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(attempt)
        task = self.session.get(TaskORM, task_id)
        if task is not None:
            task.active_resume_attempt_id = attempt.id
            task.pending_control_intent = "resume"
            task.updated_at = now
        self.session.flush()
        return _task_resume_attempt_record(attempt)

    def get_resume_attempt(self, attempt_id: str) -> TaskResumeAttemptRecord | None:
        model = self.session.get(TaskResumeAttemptORM, attempt_id)
        return _task_resume_attempt_record(model) if model else None

    def get_active_resume_attempt(self, task_id: str) -> TaskResumeAttemptRecord | None:
        model = self.session.execute(
            sa.select(TaskResumeAttemptORM)
            .where(
                TaskResumeAttemptORM.task_id == task_id,
                TaskResumeAttemptORM.status.in_(["queued", "leased", "restoring", "running", "blocked"]),
            )
            .order_by(TaskResumeAttemptORM.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        return _task_resume_attempt_record(model) if model else None

    def update_resume_attempt(
        self,
        attempt_id: str,
        *,
        status: str | None = None,
        lease_owner: str | None = None,
        lease_until: datetime | None = None,
        blocker_code: str | None = None,
        blocker_message: str | None = None,
    ) -> TaskResumeAttemptRecord:
        model = self.session.get(TaskResumeAttemptORM, attempt_id)
        if model is None:
            raise KeyError(f"Resume attempt {attempt_id} not found.")
        if status is not None:
            model.status = status
        if lease_owner is not None:
            model.lease_owner = lease_owner
        if lease_until is not None:
            model.lease_until = lease_until
        if blocker_code is not None:
            model.blocker_code = blocker_code
        if blocker_message is not None:
            model.blocker_message = blocker_message
        model.updated_at = utc_now()
        self.session.flush()
        return _task_resume_attempt_record(model)

    def create_work_item(self, queue: str, payload: dict[str, Any]) -> RuntimeWorkItemRecord:
        now = utc_now()
        work_item = RuntimeWorkItemORM(
            id=str(payload.get("workItemId") or new_id("work-item", queue, payload.get("taskId") or "", now.isoformat())),
            queue=queue,
            task_id=str(payload.get("taskId")) if payload.get("taskId") is not None else None,
            activity=str(payload.get("activity") or "core.agent.main.execute"),
            intent=str(payload.get("intent") or payload.get("command") or "start"),
            payload=dict(payload),
            status="queued",
            lease_owner=None,
            lease_until=None,
            attempt=max(int(payload.get("attempt") or 1), 1),
            last_error=None,
            created_at=now,
            updated_at=now,
            completed_at=None,
        )
        self.session.add(work_item)
        self.session.flush()
        return _runtime_work_item_record(work_item)

    def get_work_item(self, work_item_id: str) -> RuntimeWorkItemRecord | None:
        model = self.session.get(RuntimeWorkItemORM, work_item_id)
        return _runtime_work_item_record(model) if model else None

    def claim_work_item(self, queue: str, *, owner: str, lease_until: datetime) -> RuntimeWorkItemRecord | None:
        now = utc_now()
        statement = (
            sa.select(RuntimeWorkItemORM)
            .where(
                RuntimeWorkItemORM.queue == queue,
                RuntimeWorkItemORM.status.in_(["queued", "reclaimable", "leased"]),
                sa.or_(RuntimeWorkItemORM.lease_until.is_(None), RuntimeWorkItemORM.lease_until <= now),
            )
            .order_by(RuntimeWorkItemORM.created_at.asc(), RuntimeWorkItemORM.id.asc())
            .limit(1)
        )
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            return None
        if model.status in {"leased", "reclaimable"} or model.lease_until is not None:
            model.attempt += 1
        model.status = "leased"
        model.lease_owner = owner
        model.lease_until = lease_until
        model.updated_at = now
        self.session.flush()
        return _runtime_work_item_record(model)

    def update_work_item(
        self,
        work_item_id: str,
        *,
        status: str,
        last_error: str | None = None,
        completed_at: datetime | None = None,
    ) -> RuntimeWorkItemRecord:
        model = self.session.get(RuntimeWorkItemORM, work_item_id)
        if model is None:
            raise KeyError(f"Work item {work_item_id} not found.")
        model.status = status
        model.last_error = last_error
        model.updated_at = utc_now()
        model.completed_at = completed_at
        self.session.flush()
        return _runtime_work_item_record(model)

    def cancel_queued_work_items(self, task_id: str, *, intent: str | None = None, reason: str | None = None) -> int:
        now = utc_now()
        statement = sa.select(RuntimeWorkItemORM).where(
            RuntimeWorkItemORM.task_id == task_id,
            RuntimeWorkItemORM.status.in_(["queued", "reclaimable"]),
        )
        if intent is not None:
            statement = statement.where(RuntimeWorkItemORM.intent == intent)
        updated = 0
        for model in self.session.execute(statement).scalars().all():
            model.status = "cancelled"
            model.last_error = reason
            model.updated_at = now
            model.completed_at = now
            updated += 1
        self.session.flush()
        return updated

    def release_work_item_for_reclaim(self, work_item_id: str, *, last_error: str | None = None) -> RuntimeWorkItemRecord:
        model = self.session.get(RuntimeWorkItemORM, work_item_id)
        if model is None:
            raise KeyError(f"Work item {work_item_id} not found.")
        model.status = "reclaimable"
        model.last_error = last_error
        model.lease_owner = None
        model.lease_until = None
        model.updated_at = utc_now()
        self.session.flush()
        return _runtime_work_item_record(model)

    def create_task_branch(self, payload: dict[str, Any]) -> TaskBranchRecord:
        now = utc_now()
        branch = TaskBranchORM(
            id=str(payload.get("id") or new_id("task-branch", payload.get("parentTaskId"), payload.get("sourceSnapshotId"), now.isoformat())),
            parent_task_id=str(payload["parentTaskId"]),
            child_task_id=str(payload["childTaskId"]),
            source_snapshot_id=str(payload["sourceSnapshotId"]),
            source_snapshot_checksum=str(payload["sourceSnapshotChecksum"]),
            label=str(payload.get("label")) if payload.get("label") is not None else None,
            created_by_user_id=str(payload.get("createdByUserId") or "operator"),
            created_at=now,
        )
        self.session.add(branch)
        self.session.flush()
        return _task_branch_record(branch)

