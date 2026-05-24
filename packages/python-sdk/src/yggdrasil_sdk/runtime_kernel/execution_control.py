from ._common import *  # noqa: F403,F401
from .root_mount import *  # noqa: F403,F401
from .snapshot import *  # noqa: F403,F401
from .takeover import *  # noqa: F403,F401


def record_task_side_channel_event(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        event = runtime_repository.create_side_channel_event(
            {
                **request,
                "taskId": task.id,
                "projectId": request.get("projectId") or task.project_id,
            }
        )
    return {"sideChannelEvent": event.model_dump(by_alias=True, mode="json")}


def post_task_mailbox_message(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    should_queue = False
    wake_request = dict(request.get("wakeRequest") or {}) if isinstance(request.get("wakeRequest"), dict) else {}
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        message = runtime_repository.create_mailbox_message(
            {
                **request,
                "taskId": task.id,
                "projectId": request.get("projectId") or task.project_id,
            }
        )
        side_channel_event = runtime_repository.create_side_channel_event(
            {
                "taskId": task.id,
                "projectId": task.project_id,
                "agentRunId": request.get("agentRunId"),
                "source": request.get("sender") or request.get("createdBy") or {"type": "agent", "id": "system"},
                "eventKind": f"mailbox.{message.message_kind}",
                "level": "info",
                "summary": normalize_excerpt(message.subject or message.body or "Mailbox message recorded.", 240),
                "workTreeNodeId": message.work_tree_node_id,
                "payloadRef": request.get("payloadRef"),
            }
        )
        latest_active_run = task_repository.get_latest_agent_run(
            task_id,
            statuses={"initializing", "mounting", "running", "waiting-tool", "draining", "pausing"},
        )
        mailbox_state = runtime_repository.get_mailbox_state(task_id)
        wake_request.setdefault("mailboxState", mailbox_state)
        if message.work_tree_node_id is not None:
            memory_retrieval_state = dict(wake_request.get("memoryRetrievalState") or {})
            memory_retrieval_state.setdefault("workTreeNodeId", message.work_tree_node_id)
            wake_request["memoryRetrievalState"] = memory_retrieval_state
        should_queue = bool(
            message.wake_on_message
            and task.status in {"draft", "queued"}
            and not task.pause_requested
            and latest_active_run is None
        )
    wake_result = queue_main_agent_execution(task_id, wake_request) if should_queue else None
    return {
        "mailboxMessage": message.model_dump(by_alias=True, mode="json"),
        "mailboxState": mailbox_state,
        "sideChannelEvent": side_channel_event.model_dump(by_alias=True, mode="json"),
        "wakeResult": wake_result,
    }

def queue_main_agent_execution(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    command = str(request.get("command") or "start")
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        update_payload: dict[str, Any] = {}
        outbox_record = None
        for key in ("currentFocus", "currentObjective", "resumeMessage", "budget", "budgetState"):
            if key in request:
                update_payload[key] = request[key]
        if command == "resume":
            if task.status != "paused":
                raise ValueError(f"Task {task_id} is not paused and cannot be resumed.")
            snapshot = None
            if request.get("resumeToken") is not None:
                snapshot = task_repository.get_snapshot_by_resume_token(str(request["resumeToken"]))
            elif task.active_snapshot_id:
                snapshot = task_repository.get_snapshot(task.active_snapshot_id)
            if snapshot is None or snapshot.status != "restorable":
                raise ValueError(f"Task {task_id} does not have a restorable snapshot.")
            update_payload["status"] = "queued"
            update_payload["pauseRequested"] = False
            update_payload["resumeMessage"] = request.get("resumeMessage") or snapshot.resume_message or task.resume_message
            resume_request_locator = f"agent-runtime/tasks/{task.id}/resume-requests/{new_id('resume', task.id)}"
            resume_request_payload = {
                "requestedBy": request.get("requestedBy") or {"type": "user", "id": "operator"},
                "reason": request.get("reason") or "manual-resume",
                "resumeToken": request.get("resumeToken") or snapshot.resume_token,
                "resumeMessage": update_payload["resumeMessage"],
                "requestedAt": utc_now().isoformat(),
            }
            _cache_package_entry(coordinator, resume_request_locator, resume_request_payload)
            outbox_record = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="task",
                aggregate_id=task.id,
                event_type="task.resume.requested",
                locator=resume_request_locator,
            )
        else:
            if task.status in {"paused", "completed", "failed", "cancelled"}:
                raise ValueError(f"Task {task_id} is in state {task.status} and cannot be started directly.")
            update_payload["status"] = "queued"
        task = task_repository.update_task(task_id, update_payload)
        work_item = {
            "activity": "core.agent.main.execute",
            "taskId": task_id,
            "command": command,
            "requestedAt": utc_now().isoformat(),
            "payload": request,
        }
        queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, work_item)
    return {
        "status": "queued",
        "queue": AGENT_RUNTIME_QUEUE,
        "queueDepth": queue_depth,
        "task": task.model_dump(by_alias=True, mode="json"),
        "workItem": work_item,
        "outboxRecord": outbox_record.model_dump(by_alias=True, mode="json") if outbox_record is not None else None,
    }

def request_task_pause(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        next_status = task.status
        if task.status == "running":
            next_status = "pause-requested"
        task = task_repository.update_task(
            task_id,
            {
                "status": next_status,
                "pauseRequested": True,
                "resumeMessage": request.get("resumeMessage") or task.resume_message,
                "currentFocus": request.get("currentFocus") or task.current_focus,
            },
        )
        pause_request_payload = {
            "requestedBy": request.get("requestedBy") or {"type": "user", "id": "operator"},
            "reason": request.get("reason") or "manual-pause",
            "pauseMode": request.get("pauseMode") or "manual",
            "waitForSafeStop": bool(request.get("waitForSafeStop", True)),
            "resumeMessage": request.get("resumeMessage"),
            "requestedAt": utc_now().isoformat(),
        }
        pause_request_locator = f"agent-runtime/tasks/{task.id}/pause-requests/{new_id('pause', task.id)}"
        coordinator = RedisCoordinator(runtime.settings)
        _cache_package_entry(coordinator, pause_request_locator, pause_request_payload)
        _cache_package_entry(coordinator, f"runtime/tasks/{task_id}/pause-request/current", pause_request_payload)
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.pause.requested",
            locator=pause_request_locator,
        )
    return {
        "status": "pause-requested",
        "task": task.model_dump(by_alias=True, mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def _latest_takeover_protocol(task_repository: TaskRepository, task_id: str) -> tuple[Any | None, TaskTakeoverProtocol | None]:
    latest_run = task_repository.get_latest_agent_run(task_id)
    if latest_run is None:
        return None, None
    return latest_run, load_persisted_task_takeover_protocol(task_id, latest_run.id)


def approve_task_completion(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        if task.status != "awaiting-approval":
            raise ValueError(f"Task {task_id} is in state {task.status} and cannot be approved.")

        latest_run, takeover_protocol = _latest_takeover_protocol(task_repository, task_id)
        takeover_ref = None
        if takeover_protocol is not None and latest_run is not None:
            takeover_protocol = approve_takeover_completion(takeover_protocol)
            if takeover_protocol is not None:
                takeover_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=latest_run.id)

        task = task_repository.update_task(
            task_id,
            {
                "status": "completed",
                "pauseRequested": False,
                "activeSnapshotId": None,
                "currentFocus": request.get("currentFocus") or "completed",
            },
        )
        approval_locator = f"agent-runtime/tasks/{task.id}/approval/{new_id('approval', task.id)}"
        _cache_package_entry(
            coordinator,
            approval_locator,
            {
                "taskId": task.id,
                "approvedAt": utc_now().isoformat(),
                "approvedBy": request.get("approvedBy") or {"type": "user", "id": "operator"},
                "runId": latest_run.id if latest_run is not None else None,
                "takeoverProtocolRef": takeover_ref.model_dump(mode="json") if takeover_ref is not None else None,
            },
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.completion.approved",
            locator=approval_locator,
        )
    return {
        "status": "completed",
        "task": task.model_dump(by_alias=True, mode="json"),
        "takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
        "takeoverProtocolRef": takeover_ref.model_dump(mode="json") if takeover_ref is not None else None,
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def request_task_revision(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = dict(payload or {})
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        if task.status != "awaiting-approval":
            raise ValueError(f"Task {task_id} is in state {task.status} and cannot be reopened for revision.")

        latest_run, takeover_protocol = _latest_takeover_protocol(task_repository, task_id)
        if takeover_protocol is None:
            raise ValueError(f"Task {task_id} does not have a persisted takeover protocol to reopen.")
        revision_target_node_id = str(request.get("nodeId") or "").strip() or None
        revision_reason = str(request.get("reason") or request.get("resumeMessage") or "revision-requested").strip() or None
        reopened_protocol, reopened_stack = reopen_takeover_work_node_for_revision(
            takeover_protocol,
            task_id=task.id,
            agent_run_id=latest_run.id if latest_run is not None else new_id("run", task.id, "revision-preview"),
            node_id=revision_target_node_id,
            revision_reason=revision_reason,
            work_context_stack=request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None,
        )
        takeover_ref = persist_task_takeover_protocol(
            reopened_protocol,
            task_id=task.id,
            run_id=latest_run.id if latest_run is not None else new_id("run", task.id, "revision-state", stable=True),
        )
        request.setdefault("currentObjective", task.current_objective or reopened_protocol.objective)
        request.setdefault("taskObjective", reopened_protocol.objective)
        request.setdefault("resumeMessage", revision_reason or f"Revise work-tree node {reopened_protocol.work_tree.current_node_id}.")
        request_payload = build_takeover_continuation_request(
            request,
            protocol=reopened_protocol,
            work_context_stack=reopened_stack,
            parent_run_id=latest_run.id if latest_run is not None else None,
            current_focus=request.get("currentFocus") or _work_tree_focus_label(reopened_protocol),
        )
        task = task_repository.update_task(
            task_id,
            {
                "status": "queued",
                "pauseRequested": False,
                "activeSnapshotId": None,
                "currentFocus": request_payload.get("currentFocus") or task.current_focus,
                "currentObjective": request_payload.get("currentObjective") or task.current_objective,
                "resumeMessage": request_payload.get("resumeMessage") or task.resume_message,
            },
        )
        work_item = {
            "activity": "core.agent.main.execute",
            "taskId": task_id,
            "command": "start",
            "requestedAt": utc_now().isoformat(),
            "payload": request_payload,
        }
        queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, work_item)
        revision_locator = f"agent-runtime/tasks/{task.id}/revision-requests/{new_id('revision', task.id)}"
        _cache_package_entry(
            coordinator,
            revision_locator,
            {
                "taskId": task.id,
                "requestedAt": utc_now().isoformat(),
                "reason": revision_reason,
                "targetNodeId": reopened_protocol.work_tree.current_node_id if reopened_protocol.work_tree is not None else None,
                "takeoverProtocolRef": takeover_ref.model_dump(mode="json"),
                "queueDepth": queue_depth,
            },
        )
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.revision.requested",
            locator=revision_locator,
        )
    return {
        "status": "queued",
        "queue": AGENT_RUNTIME_QUEUE,
        "queueDepth": queue_depth,
        "task": task.model_dump(by_alias=True, mode="json"),
        "workItem": work_item,
        "takeoverProtocol": reopened_protocol.model_dump(by_alias=True, mode="json"),
        "takeoverProtocolRef": takeover_ref.model_dump(mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }

def _load_snapshot_context(snapshot: TaskSnapshotSummary | None) -> list[dict[str, Any]]:
    if snapshot is None:
        return []
    payload = load_package_entry(snapshot.context_ref.locator)
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []

def _build_execution_write_payload(
    *,
    task,
    task_type: str,
    root_mount: dict[str, Any],
    route_decision: dict[str, Any],
    model_output: str,
    model_invocation: dict[str, Any] | None,
    tool_executions: list[dict[str, Any]] | None,
    pruning_result: dict[str, Any] | None,
    resume_path: str | None,
    takeover_protocol: TaskTakeoverProtocol | None,
    takeover_protocol_ref: ExternalRef | None,
) -> dict[str, str]:
    lines = [model_output.strip() or "Model output was empty.", "", "Execution metadata:"]
    lines.extend(
        [
            f"Task goal: {task.goal}",
            f"Task objective: {task.current_objective or task.goal}",
            f"Current focus: {task.current_focus or 'runtime execution'}",
            f"Mounted summary: {root_mount['rootSummary']}",
            f"Route decision: {route_decision['selectedModel']} via {route_decision.get('selectedProvider') or 'unknown'}.",
            f"Task type: {task_type}",
        ]
    )
    if model_invocation is not None:
        lines.extend(
            [
                f"Invocation status: {model_invocation.get('status')}",
                f"Resolved model: {model_invocation.get('resolvedModel') or model_invocation.get('requestedModel')}",
                f"Resolved provider: {model_invocation.get('resolvedProvider') or 'unknown'}",
                f"Trace id: {model_invocation.get('traceId') or 'n/a'}",
                f"Prompt artifact: {model_invocation.get('promptCompileArtifactId') or 'n/a'}",
            ]
        )
    if tool_executions:
        lines.append(
            "Tool executions: "
            + "; ".join(
                f"{(execution.get('tool') or {}).get('name') or 'unknown'}={'ok' if execution.get('success') else 'error'}"
                for execution in tool_executions[:6]
                if isinstance(execution, dict)
            )
        )
    if resume_path:
        lines.append(f"Resume path: {resume_path}")
    if pruning_result is not None:
        lines.append(pruning_result.get("compressedNarrative") or pruning_result["plan"]["rationale"])
    if takeover_protocol is not None:
        lines.extend(
            [
                "",
                "Task takeover protocol:",
                f"Objective summary: {takeover_protocol.objective_summary}",
                f"Plan quality: {takeover_protocol.metrics.plan_quality_score_0_100}",
                f"Verification pass rate: {takeover_protocol.metrics.verification_pass_rate}",
                f"Delivery completeness: {takeover_protocol.metrics.delivery_completeness_score_0_100}",
            ]
        )
    if takeover_protocol_ref is not None:
        lines.append(f"Takeover artifact: {takeover_protocol_ref.locator}")
    return {
        "title": task.current_objective or task.title,
        "content": "\n".join(lines),
    }

def _record_pruning_events(session, task, plan_result: dict[str, Any], execute_result: dict[str, Any]) -> dict[str, Any]:
    planned = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="task",
        aggregate_id=task.id,
        event_type="context.pruning.planned",
        locator=f"agent-runtime/tasks/{task.id}/pruning/{plan_result['id']}",
    )
    completed = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="task",
        aggregate_id=task.id,
        event_type="context.pruning.completed",
        locator=f"agent-runtime/tasks/{task.id}/pruning/{plan_result['id']}/completed",
    )
    return {
        "planned": planned.model_dump(by_alias=True, mode="json"),
        "completed": completed.model_dump(by_alias=True, mode="json"),
    }


__all__ = [name for name in globals() if not name.startswith("__")]
