from __future__ import annotations

from typing import Any

from .catalog import load_in_process_plugin
from .contracts import ActorRef, BudgetState, EntityRef, ExternalRef, RootMountPackage, TaskSnapshotSummary
from .hooks import HookNames
from .llm_runtime import invoke_runtime_completion, load_runtime_candidate_models
from .model_routing import build_model_route_decision
from .persistence import OutboxRepository, RedisCoordinator, RuntimeRepository, TaskRepository, get_persistence_runtime, sync_module_catalog_snapshot
from .persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from .persistence.repositories import NodeRepository, WorkspaceBootstrapRepository
from .support import new_id, normalize_excerpt, utc_now


AGENT_RUNTIME_QUEUE = "agent-runtime"
PACKAGE_ENTRY_TTL_SECONDS = 60 * 60 * 24


def _normalize_budget(payload: dict[str, Any]) -> BudgetState:
    raw_budget = payload.get("budget") or payload.get("budgetState") or {}
    if isinstance(raw_budget, BudgetState):
        return raw_budget
    if not isinstance(raw_budget, dict):
        raw_budget = {}
    return BudgetState.model_validate(raw_budget)


def _normalize_entity_refs(values: Any, default_kind: str) -> list[EntityRef]:
    refs: list[EntityRef] = []
    if not isinstance(values, list):
        return refs
    for value in values:
        if isinstance(value, EntityRef):
            refs.append(value)
            continue
        if isinstance(value, dict):
            refs.append(EntityRef.model_validate(value))
            continue
        refs.append(EntityRef(kind=default_kind, id=str(value)))
    return refs


def _root_ref(project_id: str, branch_id: str, root_branch: str) -> EntityRef:
    return EntityRef(kind="node", id=new_id("node", project_id, branch_id, root_branch, stable=True))


def _active_capabilities() -> list[str]:
    snapshot = sync_module_catalog_snapshot()
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    return [
        manifest.module_id
        for manifest in snapshot.manifests
        if installs_by_module_id[manifest.module_id].desired_state == "enabled"
        and installs_by_module_id[manifest.module_id].lifecycle_state in {"active", "degraded"}
    ]


def _load_active_module(module_id: str):
    snapshot = sync_module_catalog_snapshot()
    manifests_by_module_id = {manifest.module_id: manifest for manifest in snapshot.manifests}
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    manifest = manifests_by_module_id.get(module_id)
    install = installs_by_module_id.get(module_id)
    if manifest is None or install is None or not manifest.entry_point:
        raise KeyError(f"Module not available: {module_id}")
    if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded"}:
        raise RuntimeError(f"Module {module_id} is not active.")
    plugin = load_in_process_plugin(manifest.entry_point)
    return plugin


def _call_module_hook(module_id: str, hook_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        plugin = _load_active_module(module_id)
    except Exception:
        return None
    for registration in plugin.register_hooks():
        if registration.name != hook_name:
            continue
        result = registration.handler(payload)
        if result is None:
            return {}
        if isinstance(result, dict):
            return dict(result)
        return {"items": list(result)}
    return None


def _cache_package_entry(coordinator: RedisCoordinator, locator: str, payload: Any) -> bool:
    try:
        coordinator.cache_json(locator, payload, ttl_seconds=PACKAGE_ENTRY_TTL_SECONDS)
        return True
    except Exception:
        return False


def load_package_entry(locator: str) -> Any | None:
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    try:
        return coordinator.load_json(locator)
    except Exception:
        return None


def _persist_runtime_event(
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


def _infer_task_type(task, payload: dict[str, Any]) -> str:
    explicit = payload.get("taskType")
    if explicit is not None:
        return str(explicit)
    text = " ".join(
        str(value)
        for value in [task.title, task.goal, task.current_focus, task.current_objective]
        if value is not None
    ).lower()
    if any(term in text for term in ("code", "编码", "实现", "重构", "api", "worker", "runtime")):
        return "coding"
    if any(term in text for term in ("research", "调研", "分析", "总结")):
        return "research"
    if any(term in text for term in ("maintenance", "维护", "修复", "回归")):
        return "maintenance"
    return "generic"


def _estimate_context_tokens(current_context: list[dict[str, Any]]) -> int:
    total = 0
    for item in current_context:
        if not isinstance(item, dict):
            continue
        total += max(1, len(f"{item.get('title', '')} {item.get('content', '')}".strip()) // 4)
    return total


def _estimate_usage(task, root_mount: dict[str, Any], current_context: list[dict[str, Any]], payload: dict[str, Any]) -> tuple[int, int]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    if usage.get("inputTokens") is not None or usage.get("outputTokens") is not None:
        return int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))

    source_text = " ".join(
        str(value)
        for value in [
            task.goal,
            task.current_objective,
            task.current_focus,
            root_mount.get("rootSummary"),
        ]
        if value is not None
    )
    input_tokens = max(48, len(source_text) // 4 + _estimate_context_tokens(current_context))
    output_tokens = max(24, min(256, input_tokens // 2))
    return input_tokens, output_tokens


def _remaining_cost_per_1k(budget: BudgetState, estimated_total_tokens: int) -> float | None:
    if budget.cost_budget_total is None:
        return None
    remaining_cost = budget.cost_budget_total - budget.cost_budget_used
    if remaining_cost <= 0:
        return 0.0
    if estimated_total_tokens <= 0:
        return remaining_cost
    return round((remaining_cost * 1000.0) / estimated_total_tokens, 6)


def _enforce_budget(budget: BudgetState, *, input_tokens: int, output_tokens: int, estimated_cost: float) -> None:
    estimated_total_tokens = input_tokens + output_tokens
    if budget.token_budget_total is not None and budget.token_budget_used + estimated_total_tokens > budget.token_budget_total:
        raise ValueError("Token budget exceeded before the next execution step.")
    if budget.cost_budget_total is not None and budget.cost_budget_used + estimated_cost > budget.cost_budget_total:
        raise ValueError("Cost budget exceeded before the next execution step.")


def _updated_budget_state(budget: BudgetState, *, input_tokens: int, output_tokens: int, cost_used: float) -> BudgetState:
    return budget.model_copy(
        update={
            "token_budget_used": budget.token_budget_used + input_tokens + output_tokens,
            "cost_budget_used": round(budget.cost_budget_used + cost_used, 6),
        }
    )


def build_root_mount_package(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    task_record = None
    project_id = str(request.get("projectId", DEFAULT_PROJECT_ID))
    branch_id = str(request.get("branchId", DEFAULT_BRANCH_ID))
    current_focus = request.get("currentFocus")
    task_objective = request.get("taskObjective") or request.get("currentObjective")
    resume_message = request.get("resumeMessage")
    budget_state = _normalize_budget(request)
    identity_refs = [_root_ref(project_id, branch_id, "identity")]
    context_refs = [_root_ref(project_id, branch_id, "context")]
    execution_refs = [_root_ref(project_id, branch_id, "execution")]

    try:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            task_record = task_repository.get_task(task_id)
            node_repository = NodeRepository(session)
            if task_record is not None:
                project_id = task_record.project_id
                branch_id = task_record.branch_id
                WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                    branch_id=branch_id,
                    project_id=project_id,
                    space_id=task_record.space_id,
                )
                current_focus = request.get("currentFocus") or task_record.current_focus
                task_objective = request.get("taskObjective") or request.get("currentObjective") or task_record.current_objective or task_record.goal
                resume_message = request.get("resumeMessage") or task_record.resume_message
                budget_state = BudgetState.model_validate(
                    request.get("budget") or request.get("budgetState") or task_record.budget.model_dump(by_alias=True)
                )
                identity_refs, context_refs, execution_refs = node_repository.root_mount_refs(
                    project_id,
                    branch_id,
                    task_record.execution_root_node_id,
                )
                if task_record.active_snapshot_id and not resume_message:
                    snapshot = task_repository.get_snapshot(task_record.active_snapshot_id)
                    if snapshot is not None and snapshot.resume_message:
                        resume_message = snapshot.resume_message
    except Exception:
        task_record = None

    active_capabilities = _active_capabilities()

    summary_parts = [
        "Identity root is mounted for stable agent policy.",
        "Context root is mounted for project and world state.",
        "Execution root is mounted for current task progress and resumability.",
    ]
    if current_focus:
        summary_parts.append(f"Current focus: {normalize_excerpt(str(current_focus), 120)}")
    if task_objective:
        summary_parts.append(f"Objective: {normalize_excerpt(str(task_objective), 160)}")
    if resume_message:
        summary_parts.append(f"Resume message available: {normalize_excerpt(str(resume_message), 120)}")

    package = RootMountPackage(
        id=new_id("mount", task_id, project_id, branch_id, stable=True),
        taskId=task_id,
        projectId=project_id,
        branchId=branch_id,
        systemIntro=(
            "Project Yggdrasil mounts identity, context, and execution roots before each run so "
            "the agent starts from stable runtime state instead of prompt-only conventions."
        ),
        identityRefs=identity_refs,
        contextRefs=context_refs,
        executionRefs=execution_refs,
        rootSummary=" ".join(summary_parts),
        taskObjective=str(task_objective) if task_objective is not None else None,
        resumeMessage=str(resume_message) if resume_message is not None else None,
        budgetState=budget_state,
        activeCapabilities=active_capabilities,
        generatedAt=utc_now(),
    )
    response = package.model_dump(by_alias=True, mode="json")
    response["mountedNodeRefs"] = [
        *response["identityRefs"],
        *response["contextRefs"],
        *response["executionRefs"],
    ]
    response["spaceId"] = str(request.get("spaceId", DEFAULT_SPACE_ID))
    response["source"] = "database" if task_record is not None else "preview"
    response["cached"] = _cache_package_entry(coordinator, f"runtime/tasks/{task_id}/root-mount/current", response)
    return response


def _build_pause_snapshot_state(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    request = payload or {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    project_id = str(request.get("projectId", DEFAULT_PROJECT_ID))
    branch_id = str(request.get("branchId", DEFAULT_BRANCH_ID))
    agent_run_id = str(request.get("agentRunId", new_id("run", task_id, stable=True)))
    pending_writes = _normalize_entity_refs(request.get("pendingWrites"), "node")
    pending_actions = request.get("pendingActions") if isinstance(request.get("pendingActions"), list) else []
    active_tool_calls = request.get("activeToolCalls") if isinstance(request.get("activeToolCalls"), list) else []
    current_response_state = str(request.get("currentResponseState", "completed"))
    current_context_state = request.get("currentContextState") if isinstance(request.get("currentContextState"), list) else []
    blockers: list[str] = []

    if active_tool_calls:
        blockers.append("active-tool-calls")
    if current_response_state not in {"completed", "idle", "drained"}:
        blockers.append("response-not-finished")

    safe_to_pause = not blockers
    snapshot_id = str(request.get("snapshotId") or new_id("snap", task_id, agent_run_id))
    root_mount = request.get("rootMountPreview") if isinstance(request.get("rootMountPreview"), dict) else build_root_mount_package(
        task_id,
        {
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

    snapshot = TaskSnapshotSummary(
        id=snapshot_id,
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
        pendingActions=[action for action in pending_actions if isinstance(action, dict)],
        resumeMessage=(
            str(request.get("resumeMessage"))
            if request.get("resumeMessage") is not None
            else f"Resume task {task_id} from the last safe stop."
        ),
        safeStopReason=str(request.get("safeStopReason", "manual-pause")),
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
        "projectId": project_id,
    }


def prepare_pause_snapshot(task_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
    request = payload or {}
    state = _build_pause_snapshot_state(task_id, payload)
    snapshot: TaskSnapshotSummary = state["snapshot"]
    project_id = str(state["projectId"])
    runtime = get_persistence_runtime()
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

    response = snapshot.model_dump(by_alias=True, mode="json")
    response["safeStop"] = snapshot.safe_to_pause
    response["activeToolCalls"] = state["activeToolCalls"]
    response["rootMountPreview"] = state["rootMountPreview"]
    response["flushedWrites"] = state["flushedWrites"]
    response["persisted"] = persisted
    response["rootMountCached"] = state["rootMountCached"]
    response["contextCached"] = state["contextCached"]
    return response


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
        event = _persist_runtime_event(
            session,
            project_id=task.project_id,
            aggregate_type="task",
            aggregate_id=task.id,
            event_type="task.pause.requested",
            locator=f"agent-runtime/tasks/{task.id}/pause-requests/{new_id('pause', task.id)}",
        )
        _cache_package_entry(
            RedisCoordinator(runtime.settings),
            f"runtime/tasks/{task_id}/pause-request/current",
            {
                "requestedBy": request.get("requestedBy") or {"type": "user", "id": "operator"},
                "reason": request.get("reason") or "manual-pause",
                "pauseMode": request.get("pauseMode") or "manual",
                "waitForSafeStop": bool(request.get("waitForSafeStop", True)),
                "resumeMessage": request.get("resumeMessage"),
                "requestedAt": utc_now().isoformat(),
            },
        )
    return {
        "status": "pause-requested",
        "task": task.model_dump(by_alias=True, mode="json"),
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
    pruning_result: dict[str, Any] | None,
    resume_path: str | None,
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
            ]
        )
    if resume_path:
        lines.append(f"Resume path: {resume_path}")
    if pruning_result is not None:
        lines.append(pruning_result.get("compressedNarrative") or pruning_result["plan"]["rationale"])
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


def execute_main_agent_work_item(work_item: dict[str, Any]) -> dict[str, object]:
    task_id = str(work_item.get("taskId"))
    request = work_item.get("payload") if isinstance(work_item.get("payload"), dict) else {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    lock_owner = new_id("worker", task_id, utc_now().isoformat())
    if not coordinator.acquire_lock(f"task:{task_id}", lock_owner, ttl_seconds=120):
        return {"status": "locked", "taskId": task_id}

    try:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            task_repository = TaskRepository(session)
            runtime_repository = RuntimeRepository(session)
            node_repository = NodeRepository(session)
            task = task_repository.get_task(task_id)
            if task is None:
                raise KeyError(f"Task {task_id} not found.")
            WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                branch_id=task.branch_id,
                project_id=task.project_id,
                space_id=task.space_id,
            )

            command = str(work_item.get("command") or request.get("command") or "start")
            snapshot = None
            if request.get("resumeToken") is not None:
                snapshot = task_repository.get_snapshot_by_resume_token(str(request["resumeToken"]))
            elif task.active_snapshot_id:
                snapshot = task_repository.get_snapshot(task.active_snapshot_id)
            if command == "resume" and (snapshot is None or snapshot.status != "restorable"):
                raise ValueError(f"Task {task_id} does not have a restorable snapshot.")

            current_context = request.get("currentContext") if isinstance(request.get("currentContext"), list) else _load_snapshot_context(snapshot)
            protected_items = request.get("protectedItems") if isinstance(request.get("protectedItems"), list) else []
            root_mount = build_root_mount_package(
                task_id,
                {
                    "projectId": task.project_id,
                    "branchId": task.branch_id,
                    "taskObjective": request.get("taskObjective") or task.current_objective or task.goal,
                    "currentObjective": request.get("currentObjective") or task.current_objective,
                    "currentFocus": request.get("currentFocus") or task.current_focus,
                    "resumeMessage": request.get("resumeMessage") or (snapshot.resume_message if snapshot else task.resume_message),
                    "budgetState": request.get("budgetState") or task.budget.model_dump(by_alias=True),
                },
            )

            input_tokens, output_tokens = _estimate_usage(task, root_mount, current_context, request)
            budget_limit = _remaining_cost_per_1k(task.budget, input_tokens + output_tokens)
            min_quality = float(request.get("minQuality", 0.0)) if request.get("minQuality") is not None else None
            task_type = _infer_task_type(task, request)
            runtime_candidates = load_runtime_candidate_models()
            route_preview = build_model_route_decision(
                task_type,
                task_id=task_id,
                candidates=request.get("candidateModels") if isinstance(request.get("candidateModels"), list) else runtime_candidates,
                budget_limit=budget_limit,
                required_context_window=int(request["requiredContextWindow"]) if request.get("requiredContextWindow") is not None else None,
                min_quality=min_quality,
            )
            estimated_cost = round(
                (input_tokens + output_tokens) * float(route_preview["candidateModels"][0]["costPer1k"]) / 1000.0,
                6,
            )
            _enforce_budget(task.budget, input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=estimated_cost)

            run_type = str(request.get("runType") or "main")
            parent_run_id = str(request["parentRunId"]) if request.get("parentRunId") is not None else None
            if parent_run_id is None and snapshot is not None and command == "resume":
                parent_run_id = snapshot.agent_run_id
            run_id = str(request.get("agentRunId") or new_id("run", task_id, utc_now().isoformat()))
            run = task_repository.create_agent_run(
                task_id,
                {
                    "id": run_id,
                    "parentRunId": parent_run_id,
                    "runType": run_type,
                    "status": "mounting",
                    "selectedModel": route_preview["selectedModel"],
                    "selectedProvider": route_preview.get("selectedProvider"),
                    "nextObjective": request.get("nextObjective") or task.current_objective or task.goal,
                },
            )
            route_decision = runtime_repository.create_model_route_decision(
                {
                    **route_preview,
                    "taskId": task_id,
                    "agentRunId": run.id,
                }
            )
            run = task_repository.update_agent_run(
                run.id,
                {
                    "routeDecisionId": route_decision.id,
                    "status": "running",
                },
            )
            task = task_repository.update_task(
                task_id,
                {
                    "status": "running",
                    "currentFocus": request.get("currentFocus") or task.current_focus or f"{run_type}-agent-execution",
                    "currentObjective": request.get("currentObjective") or task.current_objective or task.goal,
                    "pauseRequested": bool(task.pause_requested),
                },
            )
            run_created_event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="agent-run",
                aggregate_id=run.id,
                event_type="agent.run.created",
                locator=f"agent-runtime/tasks/{task.id}/runs/{run.id}",
            )
            route_event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="model-route-decision",
                aggregate_id=route_decision.id,
                event_type="runtime.model-route.selected",
                locator=f"agent-runtime/runtime/route-decisions/{route_decision.id}",
            )

            resume_event_payload = None
            if snapshot is not None and command == "resume":
                resumed_snapshot = task_repository.update_snapshot(snapshot.id, status="consumed", consumed_at=utc_now())
                task = task_repository.update_task(task_id, {"activeSnapshotId": None, "pauseRequested": False})
                resume_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task",
                    aggregate_id=task.id,
                    event_type="task.resumed",
                    locator=f"agent-runtime/tasks/{task.id}/resume/{run.id}",
                )
                resume_event_payload = {
                    "snapshot": resumed_snapshot.model_dump(by_alias=True, mode="json"),
                    "outboxRecord": resume_event.model_dump(by_alias=True, mode="json"),
                }

            pruning_result = None
            pruning_events = None
            if current_context:
                plan_result = _call_module_hook(
                    "context-pruning",
                    HookNames.CONTEXT_PRUNING_PLAN,
                    {
                        "taskId": task_id,
                        "sourceRunId": run.id,
                        "nextObjective": request.get("nextObjective") or task.current_objective or task.goal,
                        "budget": {
                            "maxRetainedTokens": request.get("maxRetainedTokens") or max(64, input_tokens),
                            "tokenBudgetTotal": task.budget.token_budget_total,
                        },
                        "protectedItems": protected_items,
                        "currentContext": current_context,
                    },
                )
                if plan_result is not None:
                    pruning_result = _call_module_hook(
                        "context-pruning",
                        HookNames.CONTEXT_PRUNING_EXECUTE,
                        {
                            "plan": plan_result,
                            "currentContext": current_context,
                        },
                    )
                    if pruning_result is not None:
                        pruning_events = _record_pruning_events(session, task, plan_result, pruning_result)

            execution_root_id = task.execution_root_node_id or root_mount["executionRefs"][0]["id"]
            execution_actor_id = str(request.get("executionActorId") or ("subagent" if run_type == "subagent" else "main-agent"))
            llm_result = invoke_runtime_completion(
                session,
                task=task,
                run=run,
                route_decision=route_decision,
                task_type=task_type,
                root_mount=root_mount,
                current_context=pruning_result.get("retainedItems") if isinstance(pruning_result, dict) and isinstance(pruning_result.get("retainedItems"), list) else current_context,
                request=request,
                resume_path="snapshot" if snapshot is not None and command == "resume" else None,
            )
            actual_input_tokens = int(llm_result["usage"].get("inputTokens", input_tokens))
            actual_output_tokens = int(llm_result["usage"].get("outputTokens", output_tokens))
            actual_cost = float(llm_result.get("costUsed", estimated_cost))
            run = task_repository.update_agent_run(
                run.id,
                {
                    "selectedModel": llm_result["invocation"].get("resolvedModel") or route_decision.selected_model,
                    "selectedProvider": llm_result["invocation"].get("resolvedProvider") or route_decision.selected_provider,
                    "inputTokensUsed": actual_input_tokens,
                    "outputTokensUsed": actual_output_tokens,
                    "costUsed": actual_cost,
                },
            )
            task = task_repository.update_task(
                task_id,
                {
                    "budgetState": _updated_budget_state(
                        task.budget,
                        input_tokens=actual_input_tokens,
                        output_tokens=actual_output_tokens,
                        cost_used=actual_cost,
                    ),
                },
            )
            model_invocation_event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="model-invocation",
                aggregate_id=str(llm_result["invocation"]["id"]),
                event_type="runtime.model-invocation.completed",
                locator=f"agent-runtime/runtime/model-invocations/{llm_result['invocation']['id']}",
            )
            write_payload = _build_execution_write_payload(
                task=task,
                task_type=task_type,
                root_mount=root_mount,
                route_decision=route_decision.model_dump(by_alias=True, mode="json"),
                model_output=str(llm_result["assistantText"]),
                model_invocation=llm_result["invocation"],
                pruning_result=pruning_result,
                resume_path="snapshot" if snapshot is not None and command == "resume" else None,
            )
            created_node = node_repository.create_node(
                {
                    "projectId": task.project_id,
                    "spaceId": task.space_id,
                    "branchId": task.branch_id,
                    "parentId": execution_root_id,
                    "rootBranch": "execution",
                    "nodeType": "task",
                    "title": write_payload["title"],
                    "content": write_payload["content"],
                    "createdBy": {"type": "agent", "id": execution_actor_id},
                    "updatedBy": {"type": "agent", "id": execution_actor_id},
                    "changeReason": f"{run_type}-agent-execution",
                }
            )
            write_event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="node",
                aggregate_id=created_node.id,
                event_type="node.created",
                locator=f"agent-runtime/tasks/{task.id}/writes/{created_node.id}",
            )

            if task.pause_requested or bool(request.get("pauseAfterWrite", False)):
                pause_resume_message = request.get("resumeMessage") or task.resume_message or f"Resume task {task.id} after the last safe stop."
                pause_state = _build_pause_snapshot_state(
                    task_id,
                    {
                        "projectId": task.project_id,
                        "branchId": task.branch_id,
                        "spaceId": task.space_id,
                        "agentRunId": run.id,
                        "pendingWrites": [{"kind": "node", "id": created_node.id}],
                        "pendingActions": request.get("pendingActions") if isinstance(request.get("pendingActions"), list) else [],
                        "currentResponseState": "completed",
                        "currentContextState": pruning_result.get("retainedItems") if isinstance(pruning_result, dict) else current_context,
                        "rootMountPreview": root_mount,
                        "resumeMessage": pause_resume_message,
                        "taskObjective": task.current_objective or task.goal,
                        "selectedModel": run.selected_model,
                        "selectedProvider": run.selected_provider,
                        "safeStopReason": request.get("safeStopReason") or "pause-requested",
                    },
                )
                pause_snapshot_summary: TaskSnapshotSummary = pause_state["snapshot"]
                task_repository.supersede_snapshots(task_id)
                task_repository.create_snapshot(pause_snapshot_summary)
                snapshot_created_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task-snapshot",
                    aggregate_id=pause_snapshot_summary.id,
                    event_type="task.snapshot.created",
                    locator=f"agent-runtime/tasks/{task_id}/snapshots/{pause_snapshot_summary.id}",
                )
                pause_snapshot = pause_snapshot_summary.model_dump(by_alias=True, mode="json")
                pause_snapshot["safeStop"] = pause_snapshot_summary.safe_to_pause
                pause_snapshot["activeToolCalls"] = pause_state["activeToolCalls"]
                pause_snapshot["rootMountPreview"] = pause_state["rootMountPreview"]
                pause_snapshot["flushedWrites"] = pause_state["flushedWrites"]
                pause_snapshot["persisted"] = True
                pause_snapshot["rootMountCached"] = pause_state["rootMountCached"]
                pause_snapshot["contextCached"] = pause_state["contextCached"]
                task = task_repository.update_task(
                    task_id,
                    {
                        "status": "paused",
                        "pauseRequested": False,
                        "activeSnapshotId": pause_snapshot["id"],
                        "lastSafeStopAt": utc_now(),
                        "resumeMessage": pause_snapshot["resumeMessage"],
                        "currentFocus": "paused-at-safe-stop",
                    },
                )
                run = task_repository.update_agent_run(run.id, {"status": "paused"})
                paused_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task",
                    aggregate_id=task.id,
                    event_type="task.paused",
                    locator=f"agent-runtime/tasks/{task.id}/pause/{pause_snapshot['id']}",
                )
                return {
                    "status": "paused",
                    "task": task.model_dump(by_alias=True, mode="json"),
                    "run": run.model_dump(by_alias=True, mode="json"),
                    "routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
                    "rootMount": root_mount,
                    "createdNode": created_node.model_dump(by_alias=True, mode="json"),
                    "snapshot": pause_snapshot,
                    "pruning": pruning_result,
                    "pruningEvents": pruning_events,
                    "outboxRecords": {
                        "modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
                        "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                        "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                        "snapshotCreated": snapshot_created_event.model_dump(by_alias=True, mode="json"),
                        "writeCreated": write_event.model_dump(by_alias=True, mode="json"),
                        "taskPaused": paused_event.model_dump(by_alias=True, mode="json"),
                    },
                    "resume": resume_event_payload,
                }

            task = task_repository.update_task(
                task_id,
                {
                    "status": "completed",
                    "pauseRequested": False,
                    "activeSnapshotId": None,
                    "currentFocus": request.get("nextFocus") or "completed",
                },
            )
            run = task_repository.update_agent_run(run.id, {"status": "completed"})
            return {
                "status": "completed",
                "task": task.model_dump(by_alias=True, mode="json"),
                "run": run.model_dump(by_alias=True, mode="json"),
                "routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
                "rootMount": root_mount,
                "createdNode": created_node.model_dump(by_alias=True, mode="json"),
                "pruning": pruning_result,
                "pruningEvents": pruning_events,
                "modelInvocation": llm_result["invocation"],
                "outboxRecords": {
                    "modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
                    "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                    "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                    "writeCreated": write_event.model_dump(by_alias=True, mode="json"),
                },
                "resume": resume_event_payload,
            }
    except Exception as exc:
        try:
            with runtime.session_scope() as session:
                WorkspaceBootstrapRepository(session).ensure_default_workspace()
                task_repository = TaskRepository(session)
                task = task_repository.get_task(task_id)
                if task is not None:
                    task_repository.update_task(
                        task_id,
                        {
                            "status": "failed",
                            "currentFocus": f"execution-failed: {exc}",
                        },
                    )
                    latest_run = task_repository.get_latest_agent_run(task_id, statuses={"initializing", "mounting", "running"})
                    if latest_run is not None:
                        task_repository.update_agent_run(latest_run.id, {"status": "failed"})
        except Exception:
            pass
        return {
            "status": "failed",
            "taskId": task_id,
            "detail": str(exc),
        }
    finally:
        coordinator.release_lock(f"task:{task_id}", lock_owner)
