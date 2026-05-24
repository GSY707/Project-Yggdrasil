from ._common import *
from .platform_core import WorkspaceBootstrapRepository
from ..write_queue import run_serialized_write


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
                if task.status in {"running", "pause-requested", "restarting"}:
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
            .order_by(AgentRunORM.started_at.desc())
            .limit(limit)
        )
        return [_agent_run_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_latest_agent_run(self, task_id: str, *, statuses: set[str] | None = None) -> AgentRunRecord | None:
        statement = (
            sa.select(AgentRunORM)
            .where(AgentRunORM.task_id == task_id)
            .order_by(AgentRunORM.started_at.desc())
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
            run = self.session.get(AgentRunORM, summary.agent_run_id)
            if run is None:
                raise KeyError(f"Agent run {summary.agent_run_id} not found.")
            if summary.app_id != task.app_id or summary.app_id != run.app_id:
                raise ValueError(
                    f"Snapshot appId {summary.app_id} does not match task/run app ids {task.app_id}/{run.app_id}."
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
                resume_token=summary.resume_token,
                context_ref=summary.context_ref.model_dump(mode="json"),
                root_mount_ref=summary.root_mount_ref.model_dump(mode="json"),
                pending_writes=[reference.model_dump(mode="json") for reference in summary.pending_writes],
                pending_actions=list(summary.pending_actions),
                resume_message=summary.resume_message,
                safe_stop_reason=summary.safe_stop_reason,
                created_at=summary.created_at,
                consumed_at=None,
                safe_to_pause=summary.safe_to_pause,
                current_node_id=summary.current_node_id,
                working_node_annotation=summary.working_node_annotation,
                pc_memo=summary.pc_memo,
                top_frame_id=summary.top_frame_id,
                stack_digest=summary.stack_digest,
                blockers=list(summary.blockers),
            )
            self.session.add(snapshot)
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
        statement = sa.select(TaskSnapshotORM).where(TaskSnapshotORM.resume_token == resume_token)
        model = self.session.execute(statement).scalar_one_or_none()
        return _task_snapshot_record(model) if model else None

    def update_snapshot(
        self,
        snapshot_id: str,
        *,
        status: str | None = None,
        consumed_at: datetime | None = None,
        blockers: list[str] | None = None,
    ) -> TaskSnapshotSummary:
        snapshot = self.session.get(TaskSnapshotORM, snapshot_id)
        if snapshot is None:
            raise KeyError(f"Snapshot {snapshot_id} not found.")
        if status is not None:
            snapshot.status = status
        if consumed_at is not None:
            snapshot.consumed_at = consumed_at
        if blockers is not None:
            snapshot.blockers = list(blockers)
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
                snapshot.status = "superseded"
                updated += 1
            self.session.flush()
            return updated

        return run_serialized_write(f"task-snapshot:{task_id}", _supersede)

    def list_snapshots(self, task_id: str) -> list[TaskSnapshotSummary]:
        statement = sa.select(TaskSnapshotORM).where(TaskSnapshotORM.task_id == task_id).order_by(TaskSnapshotORM.created_at.desc())
        return [_task_snapshot_record(model) for model in self.session.execute(statement).scalars().all()]

