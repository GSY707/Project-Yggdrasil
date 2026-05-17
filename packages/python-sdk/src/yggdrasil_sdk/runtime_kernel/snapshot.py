import logging
import json
from copy import deepcopy
from hashlib import sha256

from ._common import *  # noqa: F403,F401
from .root_mount import *  # noqa: F403,F401

_logger = logging.getLogger(__name__)


def _compute_snapshot_checksum(pending_action: dict[str, Any]) -> str:
    """Compute deterministic checksum for snapshot pending action payload."""
    payload = {
        key: value
        for key, value in pending_action.items()
        if key != "checksum"
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(serialized.encode("utf-8")).hexdigest()


def _verify_snapshot_integrity(pending_action: dict[str, Any]) -> tuple[bool, str | None]:
    """Verify pending action checksum and return a detailed error on mismatch."""
    expected = pending_action.get("checksum")
    if not isinstance(expected, str) or not expected.strip():
        return False, "missing-checksum"
    actual = _compute_snapshot_checksum(pending_action)
    if actual != expected:
        return False, f"checksum-mismatch: expected={expected}, actual={actual}"
    return True, None


def _int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _build_restart_request_state(request: dict[str, Any], runtime_metrics: dict[str, Any]) -> dict[str, Any]:
    request_state = {
        key: deepcopy(request.get(key))
        for key in (
            "taskType",
            "runType",
            "currentFocus",
            "currentObjective",
            "taskObjective",
            "activeCapabilities",
            "registeredTools",
            "protectedItems",
            "allowModelFallback",
            "allowToolExecution",
            "candidateModels",
            "temperature",
            "thinking",
            "reasoningEffort",
            "maxTokens",
            "maxToolRounds",
            "auditLevel",
            "maxRetainedTokens",
            "minQuality",
            "effectiveContextWindow",
            "windowRestartRatio",
            "windowRestartThreshold",
            "forcedWindowRestartBudget",
            "memoryWriteTagsEnabled",
            "responseRequirements",
            "restartMessage",
        )
        if request.get(key) is not None
    }
    for key in ("takeoverProtocol", "memoryRetrievalState", "memoryTagWrites"):
        value = request.get(key)
        if isinstance(value, dict):
            request_state[key] = deepcopy(value)
    # Keep restart/resume contract keys stable across windows, even when temporarily empty.
    request_state.setdefault("responseRequirements", deepcopy(request.get("responseRequirements")))
    request_state.setdefault("restartMessage", deepcopy(request.get("restartMessage")))
    request_state.setdefault(
        "takeoverProtocol",
        deepcopy(request.get("takeoverProtocol")) if isinstance(request.get("takeoverProtocol"), dict) else {},
    )
    request_state.setdefault(
        "memoryRetrievalState",
        deepcopy(request.get("memoryRetrievalState")) if isinstance(request.get("memoryRetrievalState"), dict) else {},
    )
    request_state.update(
        {
            "windowIndex": runtime_metrics.get("windowIndex"),
            "restartCount": runtime_metrics.get("restartCount"),
            "compressionCount": runtime_metrics.get("compressionCount"),
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens"),
            "carryForwardLossCount": runtime_metrics.get("carryForwardLossCount"),
            "forcedWindowRestartBudget": runtime_metrics.get("forcedWindowRestartBudget"),
            "runtimeMetrics": deepcopy(runtime_metrics),
        }
    )
    return request_state


def _dedupe_excerpt_sources(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for raw_value in values:
        normalized = " ".join(str(raw_value or "").split()).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _build_carry_forward_context(task_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    current_context_state = payload.get("currentContextState") if isinstance(payload.get("currentContextState"), list) else []
    if not current_context_state:
        return []

    effective_context_window = max(_int_metric(payload.get("effectiveContextWindow"), 256), 64)
    restart_threshold = max(_int_metric(payload.get("windowRestartThreshold"), effective_context_window), 32)
    carry_forward_limit = max(32, min(effective_context_window, restart_threshold - 8 if restart_threshold > 8 else restart_threshold))
    target_chars = max(160, int(carry_forward_limit * 4 * 0.55))
    item_limit = max(1, min(5, len(current_context_state)))
    per_item_chars = max(96, target_chars // item_limit)
    bullets: list[str] = []
    for item in current_context_state[:item_limit]:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("id") or "context-item")
        excerpt_source = " ".join(
            _dedupe_excerpt_sources(
                [
                    str(item.get("summary") or ""),
                    str(item.get("content") or ""),
                    str(item.get("note") or ""),
                    str(item.get("excerpt") or ""),
                ]
            )
        )
        excerpt = normalize_excerpt(excerpt_source or title, per_item_chars)
        bullets.append(f"- {title}: {excerpt}")

    source_window_index = max(_int_metric(payload.get("windowIndex"), 1), 1)
    target_window_index = source_window_index + 1
    objective = str(payload.get("currentObjective") or payload.get("taskObjective") or "Continue the current task.")
    focus = str(payload.get("currentFocus") or "window-restart")
    restart_message = str(
        payload.get("restartMessage")
        or payload.get("resumeMessage")
        or f"Continue task {task_id} from the carry-forward package."
    )
    takeover_protocol = payload.get("takeoverProtocol") if isinstance(payload.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    memory_retrieval_state = payload.get("memoryRetrievalState") if isinstance(payload.get("memoryRetrievalState"), dict) else {}
    protected_ids = [
        str(item.get("id") or "")
        for item in payload.get("protectedItems") or []
        if isinstance(item, dict) and item.get("id") is not None
    ]
    header_lines = [
        f"Window restart handoff: {source_window_index} -> {target_window_index}",
        f"Current objective: {objective}",
        f"Current focus: {focus}",
        f"Restart instruction: {restart_message}",
    ]
    if work_tree:
        header_lines.append(
            (
                "Work tree handoff: "
                f"status={work_tree.get('status')}; currentNode={work_tree.get('currentNodeId')}; "
                f"recoveryAnchor={work_tree.get('recoveryAnchor')}"
            )
        )
    if memory_retrieval_state.get("summary"):
        header_lines.append("Memory retrieval handoff: " + str(memory_retrieval_state.get("summary") or ""))
    if memory_retrieval_state.get("reverseTraceMode") and memory_retrieval_state.get("workTreeNodeId"):
        header_lines.append(f"Reverse trace mode: workTreeNode={memory_retrieval_state.get('workTreeNodeId')}")
    if protected_ids:
        header_lines.append(f"Protected refs: {', '.join(protected_ids)}")

    evidence_lines: list[str] = ["Carry-forward evidence:", *bullets]

    def _compose_content(max_evidence_lines: int, evidence_chars: int) -> str:
        capped_evidence = [evidence_lines[0], *[normalize_excerpt(line, evidence_chars) for line in evidence_lines[1:max_evidence_lines]]]
        return "\n".join([*header_lines, *capped_evidence])

    evidence_line_limit = len(evidence_lines)
    evidence_chars = per_item_chars
    content = _compose_content(evidence_line_limit, evidence_chars)
    carry_forward_item = {
        "id": new_id("carryforward", task_id, source_window_index, target_window_index),
        "title": f"Carry-forward package W{source_window_index} -> W{target_window_index}",
        "content": content,
        "kind": "carry-forward-package",
        "sourceWindowIndex": source_window_index,
        "targetWindowIndex": target_window_index,
    }

    while _estimate_context_tokens([carry_forward_item]) >= carry_forward_limit and evidence_line_limit > 2:
        evidence_line_limit -= 1
        content = _compose_content(evidence_line_limit, evidence_chars)
        carry_forward_item["content"] = content

    while _estimate_context_tokens([carry_forward_item]) >= carry_forward_limit and evidence_chars > 80:
        evidence_chars = max(80, evidence_chars // 2)
        content = _compose_content(evidence_line_limit, evidence_chars)
        carry_forward_item["content"] = content

    return [carry_forward_item]

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
    runtime_request_state = _build_restart_request_state(
        request,
        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
    )
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
            "restartMessage": request.get("restartMessage"),
            "responseRequirements": request.get("responseRequirements"),
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
            for action in [
                *pending_actions,
                *(snapshot_delta.get("pendingActions") or []),
                *(
                    [{"kind": "runtime-request-state", "requestState": runtime_request_state}]
                    if runtime_request_state
                    and not any(
                        isinstance(action, dict) and action.get("kind") == "runtime-request-state"
                        for action in [*pending_actions, *(snapshot_delta.get("pendingActions") or [])]
                    )
                    else []
                ),
            ]
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


def _build_restart_snapshot_state(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    app_id = str(request.get("appId") or DEFAULT_APP_ID)
    project_id = str(request.get("projectId", DEFAULT_PROJECT_ID))
    branch_id = str(request.get("branchId", DEFAULT_BRANCH_ID))
    agent_run_id = str(request.get("agentRunId", new_id("run", task_id, stable=True)))
    current_context_state = request.get("currentContextState") if isinstance(request.get("currentContextState"), list) else []

    try:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task = TaskRepository(session).get_task(task_id)
            if task is not None:
                app_id = task.app_id
                project_id = task.project_id
                branch_id = task.branch_id
    except Exception as exc:  # noqa: BLE001
        _logger.warning("Failed to read task record during restart snapshot build (task_id=%s): %s", task_id, exc)

    snapshot_id = str(request.get("snapshotId") or new_id("snap", task_id, agent_run_id, "restart"))
    root_mount = request.get("rootMountPreview") if isinstance(request.get("rootMountPreview"), dict) else build_root_mount_package(
        task_id,
        {
            "appId": app_id,
            "projectId": project_id,
            "branchId": branch_id,
            "spaceId": request.get("spaceId", DEFAULT_SPACE_ID),
            "taskObjective": request.get("taskObjective"),
            "resumeMessage": request.get("restartMessage") or request.get("resumeMessage"),
            "restartMessage": request.get("restartMessage"),
            "responseRequirements": request.get("responseRequirements"),
            "budget": request.get("budget") or request.get("budgetState") or {},
        },
    )
    carry_forward_context = _build_carry_forward_context(task_id, request)
    root_mount_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/root-mount"
    context_locator = f"runtime/tasks/{task_id}/snapshots/{snapshot_id}/context"
    root_mount_cached = _cache_package_entry(coordinator, root_mount_locator, root_mount)
    context_cached = _cache_package_entry(coordinator, context_locator, carry_forward_context)

    source_window_index = max(_int_metric(request.get("windowIndex"), 1), 1)
    window_span_tokens = max(_int_metric(request.get("windowSpanTokens"), _estimate_context_tokens(current_context_state)), 0)
    runtime_metrics = {
        "windowIndex": source_window_index + 1,
        "restartCount": max(_int_metric(request.get("restartCount"), 0), 0) + 1,
        "compressionCount": max(_int_metric(request.get("compressionCount"), 0), 0),
        "cumulativeWindowSpanTokens": max(_int_metric(request.get("cumulativeWindowSpanTokens"), 0), 0) + window_span_tokens,
        "carryForwardLossCount": max(_int_metric(request.get("carryForwardLossCount"), 0), 0),
        "effectiveContextWindow": max(_int_metric(request.get("effectiveContextWindow"), 0), 0),
        "windowRestartThreshold": max(_int_metric(request.get("windowRestartThreshold"), 0), 0),
        "forcedWindowRestartBudget": max(_int_metric(request.get("forcedWindowRestartBudget"), 0) - 1, 0),
        "windowSpanTokens": window_span_tokens,
    }
    if current_context_state and not carry_forward_context:
        runtime_metrics["carryForwardLossCount"] = int(runtime_metrics["carryForwardLossCount"]) + 1

    snapshot = TaskSnapshotSummary(
        id=snapshot_id,
        appId=app_id,
        taskId=task_id,
        agentRunId=agent_run_id,
        projectId=project_id,
        branchId=branch_id,
        snapshotType="restart",
        status="restorable",
        resumeToken=new_id("resume", task_id, agent_run_id, "restart", utc_now().isoformat()),
        contextRef=ExternalRef(type="package-entry", locator=context_locator),
        rootMountRef=ExternalRef(type="package-entry", locator=root_mount_locator),
        pendingWrites=[],
        pendingActions=[
            {
                "kind": "window-restart",
                "sourceWindowIndex": source_window_index,
                "targetWindowIndex": runtime_metrics["windowIndex"],
                "windowSpanTokens": window_span_tokens,
                "effectiveContextWindow": runtime_metrics["effectiveContextWindow"],
                "windowRestartThreshold": runtime_metrics["windowRestartThreshold"],
                "forcedWindowRestartBudget": runtime_metrics["forcedWindowRestartBudget"],
                "carryForwardSummary": normalize_excerpt(str(carry_forward_context[0].get("content") or ""), 240) if carry_forward_context else None,
                "requestState": _build_restart_request_state(request, runtime_metrics),
            },
            {
                "kind": "runtime-request-state",
                "requestState": _build_restart_request_state(request, runtime_metrics),
            },
        ],
        resumeMessage=str(
            request.get("restartMessage")
            or request.get("resumeMessage")
            or f"Continue task {task_id} from the carry-forward package."
        ),
        safeStopReason="context-window-restart",
        createdAt=utc_now(),
        safeToPause=True,
        blockers=[],
    )
    return {
        "snapshot": snapshot,
        "rootMountPreview": root_mount,
        "rootMountCached": root_mount_cached,
        "contextCached": context_cached,
        "projectId": project_id,
        "carryForwardContext": carry_forward_context,
        "runtimeMetrics": runtime_metrics,
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
    assistant_message: dict[str, Any] | None,
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
    if isinstance(assistant_message, dict):
        pending_action["assistantMessage"] = assistant_message
    if isinstance(request_state, dict) and request_state:
        pending_action["requestState"] = request_state
    pending_action["checksum"] = _compute_snapshot_checksum(pending_action)
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

