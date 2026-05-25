from ._base import *  # noqa: F403,F401
from yggdrasil_sdk.llm_work_analysis import analyze_llm_work_run, load_latest_task_llm_work_analysis

class TaskServiceMixin:
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

    def approve_task_completion(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        return approve_runtime_task_completion(task_id, dict(payload or {}))

    def request_task_revision(self, task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        return request_runtime_task_revision(task_id, dict(payload or {}))

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
            mailbox_messages = runtime_repository.list_mailbox_messages(task_id=task_id, limit=50)
            side_channel_events = runtime_repository.list_side_channel_events(task_id=task_id, limit=50)
            mailbox_state = runtime_repository.get_mailbox_state(task_id)
        return {
            "task": task.model_dump(by_alias=True, mode="json"),
            "agentRuns": [run.model_dump(by_alias=True, mode="json") for run in runs],
            "snapshots": [snapshot.model_dump(by_alias=True, mode="json") for snapshot in snapshots],
            "runtimeControl": self._task_runtime_control_summary(task, snapshots, runs),
            "routeDecisions": [decision.model_dump(by_alias=True, mode="json") for decision in decisions],
            "modelInvocations": [invocation.model_dump(by_alias=True, mode="json") for invocation in invocations],
            "mailboxState": mailbox_state,
            "mailboxMessages": [message.model_dump(by_alias=True, mode="json") for message in mailbox_messages],
            "sideChannelEvents": [event.model_dump(by_alias=True, mode="json") for event in side_channel_events],
        }

    def get_latest_task_llm_work_analysis(self, task_id: str, *, granularity: str | None = None) -> dict[str, object]:
        try:
            return load_latest_task_llm_work_analysis(
                task_id,
                granularities=granularity,
                workspace_root=self.workspace_root,
            )
        except KeyError:
            self.get_task(task_id)
            return analyze_llm_work_run(
                task_id=task_id,
                granularities=granularity,
                persist=True,
                workspace_root=self.workspace_root,
            )

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

    def list_task_mailbox_messages(self, task_id: str, *, status: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            runtime_repository = RuntimeRepository(session)
            messages = runtime_repository.list_mailbox_messages(task_id=task_id, status=status, limit=limit)
            mailbox_state = runtime_repository.get_mailbox_state(task_id)
        return {
            "mailboxState": mailbox_state,
            "mailboxMessages": [message.model_dump(by_alias=True, mode="json") for message in messages],
        }

    def post_task_mailbox_message(self, task_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return post_runtime_task_mailbox_message(task_id, dict(payload or {}))

    def list_task_side_channel_events(
        self,
        task_id: str,
        *,
        agent_run_id: str | None = None,
        level: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            events = RuntimeRepository(session).list_side_channel_events(
                task_id=task_id,
                agent_run_id=agent_run_id,
                level=level,
                limit=limit,
            )
        return {"sideChannelEvents": [event.model_dump(by_alias=True, mode="json") for event in events]}

    def post_task_side_channel_event(self, task_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return post_runtime_side_channel_event(task_id, dict(payload or {}))

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


