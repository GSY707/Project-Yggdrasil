import logging

from ._common import *  # noqa: F403,F401
from .root_mount import *  # noqa: F403,F401

_logger = logging.getLogger(__name__)

def _build_pause_snapshot_state(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    app_id = str(request.get("appId") or DEFAULT_APP_ID)
    project_id = str(request.get("projectId", DEFAULT_PROJECT_ID))
    branch_id = str(request.get("branchId", DEFAULT_BRANCH_ID))
    agent_run_id = str(request.get("agentRunId", new_id("run", task_id, stable=True)))
    pending_writes = _normalize_entity_refs(request.get("pendingWrites"), "node")
    pending_actions = request.get("pendingActions") if isinstance(request.get("pendingActions"), list) else []
    active_tool_calls = request.get("activeToolCalls") if isinstance(request.get("activeToolCalls"), list) else []
    current_response_state = str(request.get("currentResponseState", "completed"))
    current_context_state = request.get("currentContextState") if isinstance(request.get("currentContextState"), list) else []
    blockers: list[str] = []

    try:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task = TaskRepository(session).get_task(task_id)
            if task is not None:
                app_id = task.app_id
                project_id = task.project_id
                branch_id = task.branch_id
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Failed to read task record during pause snapshot build (task_id=%s): %s", task_id, exc)

    if active_tool_calls:
        blockers.append("active-tool-calls")
    if current_response_state not in {"completed", "idle", "drained"}:
        blockers.append("response-not-finished")

    snapshot_id = str(request.get("snapshotId") or new_id("snap", task_id, agent_run_id))
    root_mount = request.get("rootMountPreview") if isinstance(request.get("rootMountPreview"), dict) else build_root_mount_package(
        task_id,
        {
            "appId": app_id,
            "projectId": project_id,
            "branchId": branch_id,
            "spaceId": request.get("spaceId", DEFAULT_SPACE_ID),
            "taskObjective": request.get("taskObjective"),
            "resumeMessage": request.get("resumeMessage"),
            "budget": request.get("budget") or request.get("budgetState") or {},
        },
    )
    root_mount_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/root-mount"
    context_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/context"
    root_mount_cached = _cache_package_entry(coordinator, root_mount_locator, root_mount)
    context_cached = _cache_package_entry(coordinator, context_locator, current_context_state)

    snapshot_delta: dict[str, Any] = {}
    module_summaries: list[str] = []
    pause_active_capabilities = resolve_application_active_capabilities(app_id=app_id)
    pause_results = collect_hook_results(
        HookNames.TASK_PAUSE_PREPARE,
        {
            "taskId": task_id,
            "taskState": {
                "projectId": project_id,
                "branchId": branch_id,
                "spaceId": request.get("spaceId", DEFAULT_SPACE_ID),
                "agentRunId": agent_run_id,
            },
            "pendingWrites": [reference.model_dump(mode="json") for reference in pending_writes],
            "pendingActions": pending_actions,
            "activeToolCalls": [str(tool_call) for tool_call in active_tool_calls],
            "currentResponseState": current_response_state,
            "currentContextState": current_context_state,
            "rootMountPreview": root_mount,
        },
        module_ids=pause_active_capabilities,
    )
    for item in pause_results:
        module_id = str(item.get("moduleId") or "unknown")
        if item.get("error"):
            blockers.append(f"{module_id}:{item['error']}")
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        if isinstance(result.get("snapshotDelta"), dict):
            snapshot_delta.update(result["snapshotDelta"])
        if isinstance(result.get("blockers"), list):
            blockers.extend(str(blocker) for blocker in result["blockers"])
        if result.get("safeToPause") is False:
            blockers.append(f"{module_id}:unsafe")
        if result.get("summary") is not None:
            module_summaries.append(str(result["summary"]))

    safe_to_pause = not blockers

    snapshot = TaskSnapshotSummary(
        id=snapshot_id,
        appId=app_id,
        taskId=task_id,
        agentRunId=agent_run_id,
        projectId=project_id,
        branchId=branch_id,
        snapshotType="pause",
        status="restorable" if safe_to_pause else "created",
        resumeToken=str(request.get("resumeToken") or new_id("resume", task_id, agent_run_id)),
        contextRef=ExternalRef(type="package-entry", locator=context_locator),
        rootMountRef=ExternalRef(type="package-entry", locator=root_mount_locator),
        pendingWrites=pending_writes,
        pendingActions=[
            action
            for action in [*pending_actions, *(snapshot_delta.get("pendingActions") or [])]
            if isinstance(action, dict)
        ],
        resumeMessage=(
            str(snapshot_delta.get("resumeMessage"))
            if snapshot_delta.get("resumeMessage") is not None
            else str(request.get("resumeMessage"))
            if request.get("resumeMessage") is not None
            else f"Resume task {task_id} from the last safe stop."
        ),
        safeStopReason=str(snapshot_delta.get("safeStopReason") or request.get("safeStopReason", "manual-pause")),
        createdAt=utc_now(),
        safeToPause=safe_to_pause,
        blockers=blockers,
    )
    return {
        "snapshot": snapshot,
        "rootMountPreview": root_mount,
        "activeToolCalls": [str(tool_call) for tool_call in active_tool_calls],
        "flushedWrites": len(pending_writes),
        "rootMountCached": root_mount_cached,
        "contextCached": context_cached,
        "moduleSummaries": module_summaries,
        "projectId": project_id,
    }

def prepare_pause_snapshot(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    state = _build_pause_snapshot_state(task_id, payload)
    snapshot: TaskSnapshotSummary = state["snapshot"]
    project_id = str(state["projectId"])
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    lock_owner = new_id("pause", task_id)
    if not coordinator.acquire_lock(f"task:{task_id}", lock_owner, ttl_seconds=30):
        response = snapshot.model_dump(by_alias=True, mode="json")
        response["safeStop"] = snapshot.safe_to_pause
        response["activeToolCalls"] = state["activeToolCalls"]
        response["rootMountPreview"] = state["rootMountPreview"]
        response["flushedWrites"] = state["flushedWrites"]
        response["persisted"] = False
        response["rootMountCached"] = state["rootMountCached"]
        response["contextCached"] = state["contextCached"]
        response["moduleSummaries"] = state.get("moduleSummaries") or []
        return response
    persisted = False
    try:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            task = task_repository.get_task(task_id)
            if task is not None:
                if task_repository.get_agent_run(snapshot.agent_run_id) is None:
                    task_repository.create_agent_run(
                        task_id,
                        {
                            "id": snapshot.agent_run_id,
                            "status": "paused" if snapshot.safe_to_pause else "running",
                            "selectedModel": request.get("selectedModel") or "gpt-5.4",
                            "selectedProvider": request.get("selectedProvider") or "copilot",
                            "nextObjective": request.get("nextObjective") or request.get("resumeMessage"),
                        },
                    )
                task_repository.supersede_snapshots(task_id)
                task_repository.create_snapshot(snapshot)
                _persist_runtime_event(
                    session,
                    project_id=project_id,
                    aggregate_type="task-snapshot",
                    aggregate_id=snapshot.id,
                    event_type="task.snapshot.created",
                    locator=f"agent-runtime/tasks/{task_id}/snapshots/{snapshot.id}",
                )
                persisted = True
    except Exception:
        persisted = False
    finally:
        coordinator.release_lock(f"task:{task_id}", lock_owner)

    response = snapshot.model_dump(by_alias=True, mode="json")
    response["safeStop"] = snapshot.safe_to_pause
    response["activeToolCalls"] = state["activeToolCalls"]
    response["rootMountPreview"] = state["rootMountPreview"]
    response["flushedWrites"] = state["flushedWrites"]
    response["persisted"] = persisted
    response["rootMountCached"] = state["rootMountCached"]
    response["contextCached"] = state["contextCached"]
    response["moduleSummaries"] = state.get("moduleSummaries") or []
    return response


def save_pending_tool_calls_snapshot(
    task_id: str,
    *,
    agent_run_id: str,
    pending_tool_calls: list[dict[str, Any]],
    conversation_messages: list[dict[str, Any]],
    invocation_id: str,
    round_index: int,
    usage_totals: dict[str, int],
    accumulated_cost: float,
    round_summaries: list[dict[str, Any]],
    round_modes: list[str],
    current_context_state: list[dict[str, Any]],
    root_mount_preview: dict[str, Any] | None = None,
    app_id: str | None = None,
    project_id: str | None = None,
    branch_id: str | None = None,
    lock_already_held: bool = False,
    session_override: Any | None = None,
    request_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Save a restorable snapshot with pending tool calls that were interrupted by a safe shutdown."""
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    snapshot_id = new_id("snap", task_id, agent_run_id)
    resume_token = new_id("resume", task_id, agent_run_id)

    resolved_app_id = str(app_id or DEFAULT_APP_ID)
    resolved_project_id = str(project_id or DEFAULT_PROJECT_ID)
    resolved_branch_id = str(branch_id or DEFAULT_BRANCH_ID)

    root_mount = root_mount_preview if isinstance(root_mount_preview, dict) else build_root_mount_package(
        task_id,
        {
            "appId": resolved_app_id,
            "projectId": resolved_project_id,
            "branchId": resolved_branch_id,
            "spaceId": DEFAULT_SPACE_ID,
            "resumeMessage": None,
            "budget": {},
        },
    )
    root_mount_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/root-mount"
    context_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/context"
    root_mount_cached = _cache_package_entry(coordinator, root_mount_locator, root_mount)
    context_cached = _cache_package_entry(coordinator, context_locator, current_context_state)

    pending_action: dict[str, Any] = {
        "kind": "pending-tool-calls",
        "invocationId": invocation_id,
        "roundIndex": round_index,
        "toolCalls": pending_tool_calls,
        "conversationMessages": conversation_messages,
        "usageTotals": usage_totals,
        "accumulatedCost": accumulated_cost,
        "roundSummaries": round_summaries,
        "roundModes": round_modes,
    }
    if isinstance(request_state, dict) and request_state:
        pending_action["requestState"] = request_state
    resume_message = (
        f"Resume task {task_id}: execute {len(pending_tool_calls)} pending tool call(s) "
        f"from round {round_index}, then continue agent loop."
    )
    snapshot = TaskSnapshotSummary(
        id=snapshot_id,
        appId=resolved_app_id,
        taskId=task_id,
        agentRunId=agent_run_id,
        projectId=resolved_project_id,
        branchId=resolved_branch_id,
        snapshotType="checkpoint",
        status="restorable",
        resumeToken=resume_token,
        contextRef=ExternalRef(type="package-entry", locator=context_locator),
        rootMountRef=ExternalRef(type="package-entry", locator=root_mount_locator),
        pendingWrites=[],
        pendingActions=[pending_action],
        resumeMessage=normalize_excerpt(resume_message, 240),
        safeStopReason="safe-shutdown-pending-tool-calls",
        createdAt=utc_now(),
        safeToPause=True,
        blockers=[],
    )

    persisted = False
    lock_owner = new_id("shutdown-snap", task_id)

    def _persist_snapshot() -> None:
        nonlocal persisted
        if session_override is not None:
            WorkspaceBootstrapRepository(session_override).ensure_default_workspace()
            task_repository = TaskRepository(session_override)
            task_repository.supersede_snapshots(task_id)
            task_repository.create_snapshot(snapshot)
            task_repository.update_task(task_id, {"activeSnapshotId": snapshot_id, "status": "paused"})
            _persist_runtime_event(
                session_override,
                project_id=resolved_project_id,
                aggregate_type="task-snapshot",
                aggregate_id=snapshot_id,
                event_type="task.snapshot.created",
                locator=f"agent-runtime/tasks/{task_id}/snapshots/{snapshot_id}",
            )
            persisted = True
            return
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            task_repository.supersede_snapshots(task_id)
            task_repository.create_snapshot(snapshot)
            task_repository.update_task(task_id, {"activeSnapshotId": snapshot_id, "status": "paused"})
            _persist_runtime_event(
                session,
                project_id=resolved_project_id,
                aggregate_type="task-snapshot",
                aggregate_id=snapshot_id,
                event_type="task.snapshot.created",
                locator=f"agent-runtime/tasks/{task_id}/snapshots/{snapshot_id}",
            )
            persisted = True

    try:
        if lock_already_held:
            _persist_snapshot()
        elif coordinator.acquire_lock(f"task:{task_id}", lock_owner, ttl_seconds=30):
            try:
                _persist_snapshot()
            finally:
                coordinator.release_lock(f"task:{task_id}", lock_owner)
    except Exception as exc:
        _logger.warning("Failed to save pending-tool-calls snapshot for task %s: %s", task_id, exc)

    result = snapshot.model_dump(by_alias=True, mode="json")
    result["persisted"] = persisted
    result["rootMountCached"] = root_mount_cached
    result["contextCached"] = context_cached
    return result


__all__ = [name for name in globals() if not name.startswith('__')]

