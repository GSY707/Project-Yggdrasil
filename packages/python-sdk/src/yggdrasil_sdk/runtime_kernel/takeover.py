from __future__ import annotations
from copy import deepcopy
from typing import Any
from ..contracts import (
    ExternalRef,
    TaskRuntimeState,
    TaskTakeoverDeliverySection,
    TaskTakeoverMetrics,
    TaskTakeoverPlanStep,
    TaskTakeoverProtocol,
    TaskTakeoverVerificationItem,
    WorkContextChildCompletionSummary,
    WorkContextFrame,
    WorkContextStack,
    WorkTreeNode,
    WorkTreeProtocol,
)
from ..hook_runtime import collect_hook_results
from ..hooks import HookNames
from ..support import (
    ensure_state_subdir,
    new_id,
    normalize_excerpt,
    read_json,
    relative_workspace_path,
    resolve_workspace_root,
    utc_now,
    write_json,
)
from .work_tree_graph import compute_delivery_readiness
_WORK_TREE_PHASE_MAP = {
    "objective": "planning",
    "constraints": "planning",
    "plan": "planning",
    "execute": "executing",
    "verify": "verification",
    "deliver": "delivery",
}
_TAKEOVER_CONFIRMATION_KEYS: tuple[str, ...] = (
    "takeoverPlanConfirmed",
    "planConfirmed",
    "confirmPlan",
)
def _work_tree_status(protocol_status: str) -> str:
    if protocol_status == "completed":
        return "completed"
    if protocol_status == "verified":
        return "verified"
    if protocol_status == "executing":
        return "active"
    return "planned"
def _work_tree_from_protocol_parts(
    *,
    task_id: str,
    objective: str,
    constraints: list[Any],
    plan: list[Any],
    protocol_status: str,
) -> WorkTreeProtocol:
    constraint_ids = []
    for item in constraints:
        if hasattr(item, "id"):
            constraint_ids.append(str(item.id))
        elif isinstance(item, dict) and item.get("id"):
            constraint_ids.append(str(item["id"]))

    nodes: list[WorkTreeNode] = []
    first_active_index: int | None = None
    for index, step in enumerate(plan):
        normalized = step.model_dump(by_alias=True, mode="json") if hasattr(step, "model_dump") else dict(step)
        step_id = str(normalized.get("id") or new_id("work-tree-step", task_id, index, stable=True))
        status = str(normalized.get("status") or "pending")
        if status == "pending" and first_active_index is None:
            status = "in-progress"
            first_active_index = index
        elif status == "in-progress" and first_active_index is None:
            first_active_index = index
        node = WorkTreeNode(
            id=new_id("work-tree-node", task_id, step_id, stable=True),
            title=str(normalized.get("title") or f"step-{index + 1}"),
            phase=_WORK_TREE_PHASE_MAP.get(str(normalized.get("phase") or "plan"), "planning"),
            status=status,
            planStepIds=[step_id],
            constraintIds=constraint_ids,
            dependsOn=[str(item) for item in normalized.get("dependsOn") or []],
            expectedEvidence=[str(item) for item in normalized.get("expectedEvidence") or []],
            recoveryAnchor=f"resume:{step_id}" if str(normalized.get("phase") or "") == "execute" else None,
        )
        nodes.append(node)

    if not nodes:
        nodes.append(
            WorkTreeNode(
                id=new_id("work-tree-node", task_id, "bootstrap", stable=True),
                title="Establish executable plan",
                phase="planning",
                status="in-progress",
                planStepIds=[],
                constraintIds=constraint_ids,
                dependsOn=[],
                expectedEvidence=["normalized objective", "constraint baseline"],
                recoveryAnchor="resume:bootstrap",
            )
        )

    current_node = next((node for node in nodes if node.status in {"in-progress", "blocked", "pending"}), None)
    entropy_budget_remaining = max(0, 12 - len(nodes) - len(constraint_ids))
    return WorkTreeProtocol(
        taskId=task_id,
        rootObjective=objective,
        status=_work_tree_status(protocol_status),
        currentNodeId=current_node.id if current_node is not None else None,
        nodes=nodes,
        recoveryAnchor=current_node.recovery_anchor if current_node is not None else None,
        entropyBudgetRemaining=entropy_budget_remaining,
    )
def _work_tree_node_index(work_tree: WorkTreeProtocol) -> dict[str, WorkTreeNode]:
    return {node.id: node for node in work_tree.nodes}
def _work_tree_active_path_node_ids(work_tree: WorkTreeProtocol, *, current_node_id: str | None = None) -> list[str]:
    node_by_id = _work_tree_node_index(work_tree)
    node_id = current_node_id or work_tree.current_node_id
    if node_id is None:
        return [item for item in work_tree.active_path_node_ids if item in node_by_id]
    path: list[str] = []
    cursor = node_by_id.get(node_id)
    visited: set[str] = set()
    while cursor is not None and cursor.id not in visited:
        path.append(cursor.id)
        visited.add(cursor.id)
        cursor = node_by_id.get(cursor.parent_node_id) if cursor.parent_node_id is not None else None
    return list(reversed(path))
def _protocol_status_from_work_tree_status(work_tree_status: str, current_status: str) -> str:
    if work_tree_status == "completed":
        return "completed"
    if work_tree_status == "awaiting-approval":
        return "verified"
    if work_tree_status == "failed":
        return "needs-clarification"
    if current_status == "needs-clarification":
        return "needs-clarification"
    if current_status == "prepared":
        return "prepared"
    return "executing"
def is_takeover_plan_confirmed(request: dict[str, Any]) -> bool:
    for key in _TAKEOVER_CONFIRMATION_KEYS:
        if key in request and bool(request.get(key)):
            return True
    return False


def _takeover_confirmation_required(request: dict[str, Any]) -> bool:
    return bool(
        request.get("requireTakeoverPlanConfirmation")
        or request.get("manualPlanConfirmationRequired")
        or request.get("dangerousPlanConfirmationRequired")
    )


def _has_required_takeover_ambiguity(protocol: TaskTakeoverProtocol) -> bool:
    return any(bool(getattr(item, "required", False)) for item in protocol.ambiguities)


def enforce_takeover_confirmation_gate(
    protocol: TaskTakeoverProtocol | None,
    *,
    request: dict[str, Any],
) -> TaskTakeoverProtocol | None:
    if protocol is None:
        return None
    confirmed = is_takeover_plan_confirmed(request)
    confirmation_required = _takeover_confirmation_required(request)
    metrics_payload = protocol.metrics.model_dump(by_alias=True, mode="json")
    metrics_payload["clarificationNeeded"] = (
        _has_required_takeover_ambiguity(protocol) or (confirmation_required and not confirmed)
    )
    metrics_payload["planConfirmationNeeded"] = confirmation_required and not confirmed
    metrics_payload["planConfirmed"] = confirmed
    if confirmed:
        if protocol.status == "needs-clarification":
            return protocol.model_copy(
                update={
                    "current_phase": "execute",
                    "status": "prepared",
                    "metrics": TaskTakeoverMetrics.model_validate(metrics_payload),
                }
            )
        return protocol.model_copy(update={"metrics": TaskTakeoverMetrics.model_validate(metrics_payload)})
    if not confirmation_required:
        return protocol.model_copy(update={"metrics": TaskTakeoverMetrics.model_validate(metrics_payload)})
    return protocol.model_copy(
        update={
            "current_phase": "confirm",
            "status": "needs-clarification",
            "metrics": TaskTakeoverMetrics.model_validate(metrics_payload),
        }
    )
def _current_work_tree_node(protocol: TaskTakeoverProtocol | None) -> WorkTreeNode | None:
    if protocol is None or protocol.work_tree is None:
        return None
    node_by_id = _work_tree_node_index(protocol.work_tree)
    if protocol.work_tree.current_node_id is not None:
        candidate = node_by_id.get(protocol.work_tree.current_node_id)
        if candidate is not None:
            return candidate
    return _fallback_work_tree_node(protocol.work_tree.nodes)
def _work_tree_focus_label(protocol: TaskTakeoverProtocol | None) -> str:
    current_node = _current_work_tree_node(protocol)
    if current_node is None:
        if protocol is None:
            return "runtime execution"
        return normalize_excerpt(protocol.objective_summary or protocol.objective, 96) or "runtime execution"
    if protocol is not None and protocol.work_tree is not None and protocol.work_tree.status == "awaiting-approval":
        return normalize_excerpt(f"等待批准: {current_node.title}", 96) or "awaiting-approval"
    local_goal = normalize_excerpt(current_node.local_goal or current_node.node_text or current_node.title, 96)
    return local_goal or current_node.title or current_node.id
def _parent_orchestration_focus_label(*, parent_node: WorkTreeNode, preferred_child: WorkTreeNode | None) -> str:
    if preferred_child is None:
        return normalize_excerpt(
            f"Parent orchestration required: continue unresolved children under {parent_node.title or parent_node.id}",
            120,
        ) or "parent-orchestration-required"
    child_label = preferred_child.local_goal or preferred_child.node_text or preferred_child.title or preferred_child.id
    return normalize_excerpt(
        f"Parent orchestration required: prioritize child {preferred_child.id} ({child_label})",
        120,
    ) or f"parent-orchestration-required:{preferred_child.id}"
def _coerce_work_context_stack(candidate: WorkContextStack | dict[str, Any] | None) -> WorkContextStack | None:
    if candidate is None:
        return None
    if isinstance(candidate, WorkContextStack):
        return candidate
    try:
        return WorkContextStack.model_validate(candidate)
    except Exception:
        return None
def normalize_takeover_runtime_state(
    protocol: TaskTakeoverProtocol | None,
    *,
    task_id: str,
    agent_run_id: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol | None, WorkContextStack | None]:
    if protocol is None:
        return None, None

    work_tree = protocol.work_tree
    if work_tree is None:
        work_tree = _work_tree_from_protocol_parts(
            task_id=task_id,
            objective=protocol.objective,
            constraints=protocol.constraints,
            plan=protocol.plan,
            protocol_status=protocol.status,
        )

    node_by_id = _work_tree_node_index(work_tree)
    current_node = node_by_id.get(str(work_tree.current_node_id)) if work_tree.current_node_id is not None else None
    if current_node is None:
        current_node = _fallback_work_tree_node(work_tree.nodes)
    if current_node is None:
        return protocol, None

    current_node_payloads: list[dict[str, Any]] = []
    now = utc_now()
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == current_node.id and payload.get("status") == "pending" and work_tree.status not in {"awaiting-approval", "completed", "failed"}:
            payload["status"] = "in-progress"
            payload["updatedAt"] = now
        current_node_payloads.append(payload)

    active_path = _work_tree_active_path_node_ids(work_tree, current_node_id=current_node.id)
    if not active_path:
        active_path = [current_node.id]
    normalized_status = work_tree.status
    if normalized_status == "planned" and current_node is not None:
        normalized_status = "active"
    normalized_work_tree = WorkTreeProtocol.model_validate(
        {
            **work_tree.model_dump(by_alias=True, mode="json"),
            "taskId": task_id,
            "currentNodeId": current_node.id,
            "nodes": current_node_payloads,
            "activePathNodeIds": active_path,
            "loadedNodeIds": [node.id for node in work_tree.nodes],
            "recoveryAnchor": current_node.recovery_anchor or work_tree.recovery_anchor,
            "pcMemo": work_tree.pc_memo or f"continue:{current_node.id}",
            "status": normalized_status,
            "updatedAt": now,
        }
    )

    stack_model = _coerce_work_context_stack(work_context_stack)
    existing_frames_by_node_id = {frame.node_id: frame for frame in stack_model.frames} if stack_model is not None else {}
    path_nodes = [node_by_id[node_id] for node_id in normalized_work_tree.active_path_node_ids if node_id in node_by_id]
    if not path_nodes:
        path_nodes = [current_node]
    frames_payload: list[dict[str, Any]] = []
    parent_frame_id: str | None = None
    for depth, node in enumerate(path_nodes):
        existing_frame = existing_frames_by_node_id.get(node.id)
        frame_payload = existing_frame.model_dump(by_alias=True, mode="json") if existing_frame is not None else {}
        frame_payload.update(
            {
                "id": frame_payload.get("id") or f"frame-{node.id}",
                "nodeId": node.id,
                "parentFrameId": parent_frame_id,
                "stackDepth": depth,
                "workingNodeAnnotation": node.working_node_annotation or f"<Working_Node: {node.id}>",
                "frameHeader": frame_payload.get("frameHeader") or node.local_goal or node.title or node.id,
                "cursorState": frame_payload.get("cursorState"),
                "status": "active" if depth == len(path_nodes) - 1 else "suspended",
            }
        )
        frames_payload.append(frame_payload)
        parent_frame_id = str(frame_payload["id"])

    normalized_stack = WorkContextStack.model_validate(
        {
            **(stack_model.model_dump(by_alias=True, mode="json") if stack_model is not None else {}),
            "taskId": task_id,
            "agentRunId": agent_run_id,
            "rootFrameId": frames_payload[0]["id"],
            "topFrameId": frames_payload[-1]["id"],
            "frames": frames_payload,
            "updatedAt": now,
        }
    )

    normalized_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": _protocol_status_from_work_tree_status(normalized_work_tree.status, protocol.status),
            "currentPhase": "deliver" if normalized_work_tree.status in {"awaiting-approval", "completed"} else "execute",
            "workTree": normalized_work_tree.model_dump(by_alias=True, mode="json"),
        }
    )
    return normalized_protocol, normalized_stack
def sync_takeover_runtime_state(
    request: dict[str, Any],
    root_mount: dict[str, Any] | None,
    protocol: TaskTakeoverProtocol | None,
    *,
    task_id: str,
    agent_run_id: str,
    current_focus: str | None = None,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol | None, WorkContextStack | None]:
    task_runtime_state = request.get("taskRuntimeState")
    if task_runtime_state is None:
        return protocol, _coerce_work_context_stack(work_context_stack)

    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=(
            work_context_stack
            if work_context_stack is not None
            else request.get("workContextStack") if isinstance(request, dict) else None
        ),
    )
    if normalized_protocol is None or normalized_protocol.work_tree is None or normalized_stack is None:
        return normalized_protocol, normalized_stack

    current_node = _current_work_tree_node(normalized_protocol)
    payload = normalized_protocol.model_dump(by_alias=True, mode="json")
    stack_payload = normalized_stack.model_dump(by_alias=True, mode="json")
    request["takeoverProtocol"] = payload
    request["workContextStack"] = stack_payload
    request["currentNodeId"] = normalized_protocol.work_tree.current_node_id
    request["workingNodeAnnotation"] = current_node.working_node_annotation if current_node is not None else None
    request["pcMemo"] = normalized_protocol.work_tree.pc_memo
    request["topFrameId"] = normalized_stack.top_frame_id
    request["stackDigest"] = normalized_stack.stack_digest
    if current_focus is not None:
        request["currentFocus"] = current_focus
    elif not str(request.get("currentFocus") or "").strip():
        request["currentFocus"] = _work_tree_focus_label(normalized_protocol)
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else None
    if memory_retrieval_state is not None:
        memory_retrieval_state["workTreeNodeId"] = normalized_protocol.work_tree.current_node_id
    if isinstance(root_mount, dict):
        root_mount["currentNodeId"] = normalized_protocol.work_tree.current_node_id
        root_mount["workingNodeAnnotation"] = current_node.working_node_annotation if current_node is not None else None
        root_mount["pcMemo"] = normalized_protocol.work_tree.pc_memo
        root_mount["topFrameId"] = normalized_stack.top_frame_id
        root_mount["stackDigest"] = normalized_stack.stack_digest
        root_mount["currentFocus"] = request.get("currentFocus")

    if isinstance(task_runtime_state, dict):
        task_runtime_state = TaskRuntimeState.model_validate(task_runtime_state)
    task_runtime_state.current_node_id = normalized_protocol.work_tree.current_node_id
    task_runtime_state.working_node_annotation = current_node.working_node_annotation if current_node is not None else None
    task_runtime_state.pc_memo = normalized_protocol.work_tree.pc_memo
    task_runtime_state.takeover_protocol = normalized_protocol
    task_runtime_state.work_context_stack = normalized_stack
    if current_focus is not None:
        task_runtime_state.current_focus = current_focus
    elif not str(task_runtime_state.current_focus or "").strip():
        task_runtime_state.current_focus = _work_tree_focus_label(normalized_protocol)
    request["taskRuntimeState"] = task_runtime_state.model_dump(by_alias=True, mode="json")

    return normalized_protocol, normalized_stack
def bootstrap_takeover_state_for_work_node(
    *,
    task_id: str,
    agent_run_id: str,
    objective: str,
    work_tree_node_id: str,
    current_focus: str | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack]:
    focus = normalize_excerpt(current_focus or objective or work_tree_node_id, 160) or work_tree_node_id
    protocol = TaskTakeoverProtocol(
        id=new_id("takeover", task_id, work_tree_node_id, stable=True),
        taskId=task_id,
        taskType="collaboration",
        runType="main",
        currentPhase="execute",
        status="executing",
        objective=objective or focus,
        objectiveSummary=normalize_excerpt(objective or focus, 160) or focus,
        ambiguities=[],
        constraints=[],
        plan=[],
        workTree=WorkTreeProtocol(
            id=new_id("worktree", task_id, work_tree_node_id, stable=True),
            taskId=task_id,
            rootNodeId=work_tree_node_id,
            rootObjective=objective or focus,
            status="active",
            currentNodeId=work_tree_node_id,
            nodes=[
                WorkTreeNode(
                    id=work_tree_node_id,
                    title=focus,
                    parentNodeId=None,
                    questionsItAnswers=[focus],
                    nodeText=focus,
                    localGoal=focus,
                    localConstraints=[],
                    localContextRefs=[],
                    workingNodeAnnotation=f"<Working_Node: {work_tree_node_id}>",
                    executionSummary=None,
                    failureSummary=None,
                    phase="coordination",
                    status="in-progress",
                    childNodeIds=[],
                    planStepIds=[],
                    constraintIds=[],
                    dependsOn=[],
                    relationIds=[],
                    expectedEvidence=["child completion summary"],
                    producedEvidenceRefs=[],
                    sourceMemoryNodeIds=[],
                    priority=0,
                    detailLevel=0,
                    recoveryAnchor=f"resume:{work_tree_node_id}",
                )
            ],
            loadedNodeIds=[work_tree_node_id],
            activePathNodeIds=[work_tree_node_id],
            pcMemo=f"continue:{work_tree_node_id}",
            recoveryAnchor=f"resume:{work_tree_node_id}",
            entropyBudgetRemaining=0,
            versionCounter=1,
        ),
        deliverySections=[],
        verificationItems=[],
        metrics=TaskTakeoverMetrics(
            planQualityScore0_100=0.0,
            reworkCount=0,
            reworkRate=0.0,
            clarificationNeeded=False,
            planConfirmationNeeded=False,
            planConfirmed=True,
            deliveryCompletenessScore0_100=0.0,
            verificationPassRate=0.0,
        ),
        appliedModules=["subagent-pr"],
        hookTrace=[],
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
    )
    if normalized_protocol is None or normalized_stack is None:
        raise ValueError(f"Failed to bootstrap takeover state for work tree node {work_tree_node_id}.")
    normalized_stack = update_cursor_state(
        normalized_stack,
        node_id=work_tree_node_id,
        cursor_state=normalize_excerpt(f"await-child:{work_tree_node_id}", 96),
    )
    return normalized_protocol, normalized_stack
def merge_child_takeover_completion_into_parent(
    parent_protocol: TaskTakeoverProtocol | None,
    *,
    parent_node_id: str | None,
    child_protocol: TaskTakeoverProtocol | None,
    child_task_id: str | None,
    child_run_id: str | None,
    child_summary: str,
    evidence_refs: list[dict[str, Any]] | None = None,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol | None, WorkContextStack | None]:
    normalized_stack = _coerce_work_context_stack(work_context_stack)
    if parent_protocol is None or parent_protocol.work_tree is None:
        return parent_protocol, normalized_stack

    target_node_id = parent_node_id or parent_protocol.work_tree.current_node_id
    if target_node_id is None:
        return parent_protocol, normalized_stack

    merged_summary = _work_tree_delivery_summary(
        child_summary,
        fallback=(child_protocol.objective_summary if child_protocol is not None else parent_protocol.objective_summary),
    )
    seen_refs: set[str] = set()
    normalized_evidence_refs: list[dict[str, Any]] = []

    def _append_ref(kind: str, ref_id: str | None) -> None:
        normalized_ref_id = str(ref_id or "").strip()
        if not normalized_ref_id:
            return
        ref_key = f"{kind}:{normalized_ref_id}"
        if ref_key in seen_refs:
            return
        seen_refs.add(ref_key)
        normalized_evidence_refs.append({"kind": kind, "id": normalized_ref_id})

    for reference in evidence_refs or []:
        if not isinstance(reference, dict):
            continue
        _append_ref(str(reference.get("kind") or "ref"), reference.get("id"))
    _append_ref("task", child_task_id)
    _append_ref("agent-run", child_run_id)
    if child_protocol is not None and child_protocol.work_tree is not None:
        _append_ref("work-tree-node", child_protocol.work_tree.current_node_id)

    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in parent_protocol.work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == target_node_id:
            existing_summary = normalize_excerpt(str(payload.get("executionSummary") or ""), 240)
            payload["executionSummary"] = normalize_excerpt(
                " ".join(part for part in (existing_summary, f"Child completion: {merged_summary}") if part),
                240,
            )
            if payload.get("status") not in {"completed", "failed", "blocked", "skipped"}:
                payload["status"] = "summarizing"
            payload["phase"] = "delivery"
            payload["updatedAt"] = now
        updated_nodes.append(payload)

    merged_work_tree = WorkTreeProtocol.model_validate(
        {
            **parent_protocol.work_tree.model_dump(by_alias=True, mode="json"),
            "currentNodeId": target_node_id,
            "pcMemo": normalize_excerpt(f"child-completion:{target_node_id}", 160),
            "status": (
                parent_protocol.work_tree.status
                if parent_protocol.work_tree.status in {"completed", "failed", "awaiting-approval"}
                else "summarizing"
            ),
            "nodes": updated_nodes,
            "updatedAt": now,
        }
    )
    merged_protocol = TaskTakeoverProtocol.model_validate(
        {
            **parent_protocol.model_dump(by_alias=True, mode="json"),
            "status": "executing" if parent_protocol.status != "completed" else parent_protocol.status,
            "currentPhase": "deliver",
            "workTree": merged_work_tree.model_dump(by_alias=True, mode="json"),
        }
    )
    if normalized_stack is not None:
        normalized_stack = append_child_completion_summary(
            normalized_stack,
            parent_node_id=target_node_id,
            child_summary=WorkContextChildCompletionSummary(
                childNodeId=child_protocol.work_tree.current_node_id if child_protocol is not None and child_protocol.work_tree is not None else (child_task_id or target_node_id),
                status="completed",
                summary=merged_summary,
                evidenceRefs=normalized_evidence_refs,
                completedAt=now,
            ),
        )
        normalized_stack = update_cursor_state(
            normalized_stack,
            node_id=target_node_id,
            cursor_state=normalize_excerpt(f"child-completion:{merged_summary}", 96),
        )
    return merged_protocol, normalized_stack
def update_cursor_state(
    work_context_stack: WorkContextStack | dict[str, Any],
    *,
    node_id: str,
    cursor_state: str | None,
) -> WorkContextStack:
    stack = WorkContextStack.model_validate(work_context_stack)
    frames_payload: list[dict[str, Any]] = []
    for frame in stack.frames:
        payload = frame.model_dump(by_alias=True, mode="json")
        if frame.node_id == node_id:
            payload["cursorState"] = cursor_state
        frames_payload.append(payload)
    return WorkContextStack.model_validate(
        {
            **stack.model_dump(by_alias=True, mode="json"),
            "frames": frames_payload,
            "updatedAt": utc_now(),
        }
    )
def append_child_completion_summary(
    work_context_stack: WorkContextStack | dict[str, Any],
    *,
    parent_node_id: str,
    child_summary: WorkContextChildCompletionSummary | dict[str, Any],
) -> WorkContextStack:
    stack = WorkContextStack.model_validate(work_context_stack)
    summary = WorkContextChildCompletionSummary.model_validate(child_summary)
    frames_payload: list[dict[str, Any]] = []
    for frame in stack.frames:
        payload = frame.model_dump(by_alias=True, mode="json")
        if frame.node_id == parent_node_id:
            existing = [
                item
                for item in payload.get("childCompletionSummaries") or []
                if str(item.get("childNodeId") or "") != summary.child_node_id
            ]
            existing.append(summary.model_dump(by_alias=True, mode="json"))
            payload["childCompletionSummaries"] = existing
        frames_payload.append(payload)
    return WorkContextStack.model_validate(
        {
            **stack.model_dump(by_alias=True, mode="json"),
            "frames": frames_payload,
            "updatedAt": utc_now(),
        }
    )
def push_work_context_frame(
    work_context_stack: WorkContextStack | dict[str, Any],
    *,
    node: WorkTreeNode | dict[str, Any],
    cursor_state: str | None = None,
) -> WorkContextStack:
    stack = WorkContextStack.model_validate(work_context_stack)
    node_model = WorkTreeNode.model_validate(node)
    frames_payload = [frame.model_dump(by_alias=True, mode="json") for frame in stack.frames]
    if frames_payload:
        frames_payload[-1]["status"] = "suspended"
    frames_payload.append(
        WorkContextFrame(
            id=f"frame-{node_model.id}",
            nodeId=node_model.id,
            parentFrameId=frames_payload[-1]["id"] if frames_payload else None,
            stackDepth=len(frames_payload),
            workingNodeAnnotation=node_model.working_node_annotation or f"<Working_Node: {node_model.id}>",
            frameHeader=node_model.local_goal or node_model.title or node_model.id,
            cursorState=cursor_state,
            status="active",
        ).model_dump(by_alias=True, mode="json")
    )
    return WorkContextStack.model_validate(
        {
            **stack.model_dump(by_alias=True, mode="json"),
            "rootFrameId": frames_payload[0]["id"],
            "topFrameId": frames_payload[-1]["id"],
            "frames": frames_payload,
            "updatedAt": utc_now(),
        }
    )
def pop_work_context_frame(
    work_context_stack: WorkContextStack | dict[str, Any],
    *,
    cursor_state: str | None = None,
    popped_status: str = "completed",
) -> WorkContextStack:
    stack = WorkContextStack.model_validate(work_context_stack)
    frames_payload = [frame.model_dump(by_alias=True, mode="json") for frame in stack.frames]
    if len(frames_payload) <= 1:
        if frames_payload:
            frames_payload[0]["status"] = "active"
            frames_payload[0]["cursorState"] = cursor_state
        return WorkContextStack.model_validate(
            {
                **stack.model_dump(by_alias=True, mode="json"),
                "frames": frames_payload,
                "updatedAt": utc_now(),
            }
        )
    frames_payload[-1]["status"] = popped_status
    frames_payload = frames_payload[:-1]
    frames_payload[-1]["status"] = "active"
    frames_payload[-1]["cursorState"] = cursor_state
    return WorkContextStack.model_validate(
        {
            **stack.model_dump(by_alias=True, mode="json"),
            "topFrameId": frames_payload[-1]["id"],
            "frames": frames_payload,
            "updatedAt": utc_now(),
        }
    )
def list_sibling_work_nodes(protocol: TaskTakeoverProtocol | None, *, node_id: str | None = None) -> list[WorkTreeNode]:
    if protocol is None or protocol.work_tree is None:
        return []
    work_tree = protocol.work_tree
    node_by_id = _work_tree_node_index(work_tree)
    target_id = node_id or work_tree.current_node_id
    if target_id is None:
        return []
    target_node = node_by_id.get(target_id)
    if target_node is None or target_node.parent_node_id is None:
        return []
    parent_node = node_by_id.get(target_node.parent_node_id)
    if parent_node is None:
        return []
    ordered_child_ids = parent_node.child_node_ids or [node.id for node in work_tree.nodes if node.parent_node_id == parent_node.id]
    return [node_by_id[item] for item in ordered_child_ids if item in node_by_id and item != target_node.id]
def pick_next_sibling_work_node(protocol: TaskTakeoverProtocol | None, *, node_id: str | None = None) -> WorkTreeNode | None:
    for preferred_status in ("in-progress", "pending", "blocked"):
        candidate = next(
            (node for node in list_sibling_work_nodes(protocol, node_id=node_id) if node.status == preferred_status),
            None,
        )
        if candidate is not None:
            return candidate
    return None
def switch_current_work_node(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    node_id: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    cursor_state: str | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack]:
    if protocol.work_tree is None:
        raise ValueError("Takeover protocol does not have a work tree.")
    work_tree = protocol.work_tree
    node_by_id = _work_tree_node_index(work_tree)
    target_node = node_by_id.get(node_id)
    if target_node is None:
        raise KeyError(f"Unknown work-tree node: {node_id}")
    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == node_id and payload.get("status") in {"pending", "blocked"}:
            payload["status"] = "in-progress"
            payload["updatedAt"] = now
        updated_nodes.append(payload)
    updated_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "executing",
            "currentPhase": "execute",
            "workTree": {
                **work_tree.model_dump(by_alias=True, mode="json"),
                "nodes": updated_nodes,
                "status": "active",
                "currentNodeId": node_id,
                "activePathNodeIds": _work_tree_active_path_node_ids(work_tree, current_node_id=node_id),
                "pcMemo": f"continue:{node_id}",
                "recoveryAnchor": target_node.recovery_anchor or work_tree.recovery_anchor,
                "updatedAt": now,
            },
        }
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        updated_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=work_context_stack,
    )
    if normalized_stack is not None and cursor_state is not None:
        normalized_stack = update_cursor_state(normalized_stack, node_id=node_id, cursor_state=cursor_state)
    if normalized_protocol is None or normalized_stack is None:
        raise ValueError("Failed to normalize work-tree runtime state.")
    return normalized_protocol, normalized_stack
def bubble_to_parent_work_node(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    node_id: str | None = None,
    cursor_state: str | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack]:
    current_node = _current_work_tree_node(protocol) if node_id is None else _work_tree_node_index(protocol.work_tree)[node_id]  # type: ignore[index]
    if current_node is None or current_node.parent_node_id is None:
        return normalize_takeover_runtime_state(protocol, task_id=task_id, agent_run_id=agent_run_id, work_context_stack=work_context_stack)  # type: ignore[return-value]
    return switch_current_work_node(
        protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        node_id=current_node.parent_node_id,
        work_context_stack=work_context_stack,
        cursor_state=cursor_state,
    )
def create_child_work_node(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    title: str,
    phase: str = "executing",
    parent_node_id: str | None = None,
    questions_it_answers: list[str] | None = None,
    local_goal: str | None = None,
    expected_evidence: list[str] | None = None,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    activate: bool = True,
    node_id: str | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack, WorkTreeNode]:
    if protocol.work_tree is None:
        raise ValueError("Takeover protocol does not have a work tree.")
    work_tree = protocol.work_tree
    current_node = _current_work_tree_node(protocol)
    target_parent_id = parent_node_id or (current_node.parent_node_id if current_node is not None and current_node.parent_node_id is not None else current_node.id if current_node is not None else work_tree.root_node_id)
    node_by_id = _work_tree_node_index(work_tree)
    parent_node = node_by_id.get(target_parent_id) if target_parent_id is not None else None
    if parent_node is None:
        raise KeyError(f"Unknown parent work-tree node: {target_parent_id}")

    new_node = WorkTreeNode(
        id=node_id or new_id("work-tree-node", task_id, target_parent_id, title),
        title=title,
        parentNodeId=target_parent_id,
        questionsItAnswers=questions_it_answers or [title],
        nodeText=local_goal or title,
        localGoal=local_goal or title,
        phase=str(phase),
        status="in-progress" if activate else "pending",
        expectedEvidence=expected_evidence or [],
        recoveryAnchor=f"resume:{target_parent_id}:{title}",
        detailLevel=max(int(parent_node.detail_level) + 1, 1),
    )

    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == parent_node.id:
            child_ids = [str(item) for item in payload.get("childNodeIds") or []]
            if new_node.id not in child_ids:
                child_ids.append(new_node.id)
            payload["childNodeIds"] = child_ids
            payload["status"] = "in-progress"
            payload["updatedAt"] = now
        updated_nodes.append(payload)
    updated_nodes.append(new_node.model_dump(by_alias=True, mode="json"))

    updated_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "executing",
            "currentPhase": "execute",
            "workTree": {
                **work_tree.model_dump(by_alias=True, mode="json"),
                "nodes": updated_nodes,
                "currentNodeId": new_node.id if activate else work_tree.current_node_id,
                "status": "active",
                "pcMemo": f"continue:{new_node.id}" if activate else work_tree.pc_memo,
                "versionCounter": int(work_tree.version_counter) + 1,
                "updatedAt": now,
            },
        }
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        updated_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=work_context_stack,
    )
    if normalized_protocol is None or normalized_stack is None:
        raise ValueError("Failed to normalize new child node runtime state.")
    return normalized_protocol, normalized_stack, new_node
def _node_children_terminal(work_tree: WorkTreeProtocol, node_id: str) -> bool:
    node_by_id = _work_tree_node_index(work_tree)
    node = node_by_id.get(node_id)
    if node is None:
        return True
    child_ids = node.child_node_ids or [item.id for item in work_tree.nodes if item.parent_node_id == node.id]
    if not child_ids:
        return True
    return all(
        node_by_id.get(child_id) is not None and node_by_id[child_id].status in {"completed", "failed", "skipped"}
        for child_id in child_ids
        if child_id in node_by_id
    )
def complete_current_work_node(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    execution_summary: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack, dict[str, Any]]:
    if protocol.work_tree is None:
        raise ValueError("Takeover protocol does not have a work tree.")
    summary = normalize_excerpt(str(execution_summary or "").strip(), 240)
    if not summary:
        raise ValueError("Current work-tree node requires a non-empty execution summary before completion.")

    work_tree = protocol.work_tree
    current_node = _current_work_tree_node(protocol)
    if current_node is None:
        raise ValueError("Takeover protocol does not have an executable current node.")
    if not _node_children_terminal(work_tree, current_node.id):
        raise ValueError(f"Work-tree node {current_node.id} still has unfinished child nodes.")

    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == current_node.id:
            produced_evidence_refs: list[dict[str, Any]] = []
            seen_refs: set[tuple[str, str]] = set()
            for ref in [*(payload.get("producedEvidenceRefs") or []), *(evidence_refs or [])]:
                if not isinstance(ref, dict):
                    continue
                kind = str(ref.get("kind") or "").strip()
                ref_id = str(ref.get("id") or "").strip()
                if not kind or not ref_id or (kind, ref_id) in seen_refs:
                    continue
                seen_refs.add((kind, ref_id))
                produced_evidence_refs.append({"kind": kind, "id": ref_id})
            payload.update(
                {
                    "status": "completed",
                    "executionSummary": summary,
                    "failureSummary": None,
                    "producedEvidenceRefs": produced_evidence_refs,
                    "updatedAt": now,
                }
            )
        updated_nodes.append(payload)

    updated_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "executing",
            "currentPhase": "execute",
            "workTree": {
                **work_tree.model_dump(by_alias=True, mode="json"),
                "nodes": updated_nodes,
                "status": "active",
                "updatedAt": now,
            },
        }
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        updated_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=work_context_stack,
    )
    if normalized_protocol is None or normalized_protocol.work_tree is None or normalized_stack is None:
        raise ValueError("Failed to normalize completed work-tree state.")

    transition = "awaiting-approval"
    current_focus = "awaiting-approval"
    next_node_id: str | None = None
    child_summary = WorkContextChildCompletionSummary(
        childNodeId=current_node.id,
        status="completed",
        summary=summary,
        summaryType="execution-result",
        evidenceRefs=evidence_refs or [],
        completedAt=now,
    )
    if current_node.parent_node_id is not None:
        normalized_stack = append_child_completion_summary(
            normalized_stack,
            parent_node_id=current_node.parent_node_id,
            child_summary=child_summary,
        )
        normalized_protocol, normalized_stack = bubble_to_parent_work_node(
            normalized_protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            work_context_stack=normalized_stack,
            node_id=current_node.id,
            cursor_state="resume-parent-after-child-completion",
        )
        transition = "bubble-parent"
        next_node_id = normalized_protocol.work_tree.current_node_id if normalized_protocol.work_tree is not None else None
        current_focus = _work_tree_focus_label(normalized_protocol)
    else:
        work_tree_payload = normalized_protocol.work_tree.model_dump(by_alias=True, mode="json")
        work_tree_payload.update(
            {
                "status": "awaiting-approval",
                "currentNodeId": normalized_protocol.work_tree.root_node_id or current_node.id,
                "pcMemo": summary,
                "updatedAt": now,
            }
        )
        normalized_protocol = TaskTakeoverProtocol.model_validate(
            {
                **normalized_protocol.model_dump(by_alias=True, mode="json"),
                "status": "verified",
                "currentPhase": "deliver",
                "workTree": WorkTreeProtocol.model_validate(work_tree_payload).model_dump(by_alias=True, mode="json"),
            }
        )
        normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
            normalized_protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            work_context_stack=normalized_stack,
        )
        if normalized_stack is not None:
            normalized_stack = update_cursor_state(
                normalized_stack,
                node_id=normalized_protocol.work_tree.current_node_id if normalized_protocol is not None and normalized_protocol.work_tree is not None else current_node.id,
                cursor_state="awaiting-approval",
            )

    result = {
        "transition": transition,
        "requiresContinuation": transition in {"continue-sibling", "bubble-parent"},
        "currentNodeId": normalized_protocol.work_tree.current_node_id if normalized_protocol.work_tree is not None else None,
        "nextNodeId": next_node_id,
        "currentFocus": current_focus,
    }
    return normalized_protocol, normalized_stack, result
def fail_current_work_node(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    failure_summary: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack, dict[str, Any]]:
    if protocol.work_tree is None:
        raise ValueError("Takeover protocol does not have a work tree.")
    failure = normalize_excerpt(str(failure_summary or "").strip(), 240)
    if not failure:
        raise ValueError("Current work-tree node requires a non-empty failure summary.")
    current_node = _current_work_tree_node(protocol)
    if current_node is None:
        raise ValueError("Takeover protocol does not have an executable current node.")
    work_tree = protocol.work_tree
    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == current_node.id:
            payload.update(
                {
                    "status": "failed",
                    "failureSummary": failure,
                    "updatedAt": now,
                }
            )
        updated_nodes.append(payload)
    next_work_tree_status = "failed" if current_node.parent_node_id is None else "active"
    failed_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "needs-clarification" if current_node.parent_node_id is None else "executing",
            "workTree": {
                **work_tree.model_dump(by_alias=True, mode="json"),
                "nodes": updated_nodes,
                "status": next_work_tree_status,
                "updatedAt": now,
            },
        }
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        failed_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=work_context_stack,
    )
    if normalized_protocol is None or normalized_stack is None:
        raise ValueError("Failed to normalize failed work-tree state.")
    if current_node.parent_node_id is None:
        return normalized_protocol, normalized_stack, {
            "transition": "failed",
            "requiresContinuation": False,
            "currentNodeId": normalized_protocol.work_tree.current_node_id if normalized_protocol.work_tree is not None else None,
            "currentFocus": normalize_excerpt(f"失败节点: {current_node.title}", 96) or "failed",
        }

    failure_child_summary = WorkContextChildCompletionSummary(
        childNodeId=current_node.id,
        status="failed",
        summary=failure,
        summaryType="failure-reason",
        evidenceRefs=[],
        completedAt=now,
    )
    normalized_stack = append_child_completion_summary(
        normalized_stack,
        parent_node_id=current_node.parent_node_id,
        child_summary=failure_child_summary,
    )
    normalized_protocol, normalized_stack = bubble_to_parent_work_node(
        normalized_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=normalized_stack,
        node_id=current_node.id,
        cursor_state="resume-parent-after-child-failure",
    )
    return normalized_protocol, normalized_stack, {
        "transition": "bubble-parent-after-failure",
        "requiresContinuation": True,
        "currentNodeId": normalized_protocol.work_tree.current_node_id if normalized_protocol.work_tree is not None else None,
        "nextNodeId": normalized_protocol.work_tree.current_node_id if normalized_protocol.work_tree is not None else None,
        "currentFocus": _work_tree_focus_label(normalized_protocol),
    }
def _check_delivery_hard_gates(protocol: TaskTakeoverProtocol) -> bool:
    """检查 hard gate 类型的 verification item 是否全部 passed。"""
    for item in protocol.verification_items:
        gate_mode = "advisory"
        status = "not-run"
        if isinstance(item, dict):
            gate_mode = item.get("gateMode", "advisory")
            status = item.get("status", "not-run")
        elif hasattr(item, "gate_mode"):
            gate_mode = item.gate_mode
            status = item.status
        if gate_mode == "hard" and status != "passed":
            return False
    return True
def _blocked_gate_labels(protocol: TaskTakeoverProtocol) -> list[str]:
    """返回所有 blocked 的 hard gate 的 label。"""
    labels: list[str] = []
    for item in protocol.verification_items:
        if isinstance(item, dict):
            if item.get("gateMode") == "hard" and item.get("status") != "passed":
                labels.append(str(item.get("label") or item.get("id") or "unknown"))
        elif hasattr(item, "gate_mode"):
            if item.gate_mode == "hard" and item.status != "passed":
                labels.append(item.label)
    return labels


def _delivery_blockers_that_survive_this_turn(
    blockers: list[str],
    *,
    evidence_refs: list[dict[str, Any]] | None,
    frontier_pressure_satisfied_by_turn_evidence: bool = False,
) -> list[str]:
    result: list[str] = []
    has_turn_evidence = _has_turn_evidence(evidence_refs)
    for blocker in blockers:
        normalized = str(blocker or "").strip()
        if not normalized or normalized == "target-not-summarized":
            continue
        if normalized != "missing-target-evidence":
            continue
        if frontier_pressure_satisfied_by_turn_evidence:
            continue
        if has_turn_evidence:
            continue
        result.append(normalized)
    return list(dict.fromkeys(result))


def _has_turn_evidence(evidence_refs: list[dict[str, Any]] | None) -> bool:
    return any(
        isinstance(item, dict) and str(item.get("kind") or "").strip() and str(item.get("id") or "").strip()
        for item in evidence_refs or []
    )


def _frontier_satisfied_by_turn_evidence(
    frontier: dict[str, Any],
    *,
    evidence_refs: list[dict[str, Any]] | None,
) -> bool:
    if not _has_turn_evidence(evidence_refs):
        return False
    return str(frontier.get("id") or "").endswith(":missing-evidence")


def _frontiers_that_survive_this_turn(
    frontiers: list[Any],
    *,
    evidence_refs: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], bool]:
    raw_open_frontiers = [
        dict(item)
        for item in frontiers
        if isinstance(item, dict) and str(item.get("status") or "open") == "open"
    ]
    surviving_frontiers = [
        dict(item)
        for item in frontiers
        if isinstance(item, dict)
        and not _frontier_satisfied_by_turn_evidence(item, evidence_refs=evidence_refs)
    ]
    surviving_open_frontiers = [
        item for item in surviving_frontiers if str(item.get("status") or "open") == "open"
    ]
    frontier_pressure_satisfied = bool(raw_open_frontiers) and not surviving_open_frontiers
    return surviving_frontiers, frontier_pressure_satisfied


def advance_takeover_after_delivery(
    protocol: TaskTakeoverProtocol | None,
    *,
    task_id: str,
    agent_run_id: str,
    assistant_text: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    work_tree_resolution: dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol | None, WorkContextStack | None, dict[str, Any]]:
    if protocol is None:
        return None, None, {"transition": "completed", "requiresContinuation": False, "currentFocus": "completed"}
    if protocol.status == "completed" or (protocol.work_tree is not None and protocol.work_tree.status == "completed"):
        return protocol, work_context_stack, {
            "transition": "completed",
            "requiresContinuation": False,
            "currentNodeId": protocol.work_tree.current_node_id if protocol.work_tree is not None else None,
            "nextNodeId": None,
            "currentFocus": "completed",
        }

    current_node = _current_work_tree_node(protocol)
    if protocol.work_tree is not None and current_node is not None:
        node_by_id = _work_tree_node_index(protocol.work_tree)
        child_ids = current_node.child_node_ids or [
            node.id
            for node in protocol.work_tree.nodes
            if node.parent_node_id == current_node.id
        ]
        pending_child_ids = [
            child_id
            for child_id in child_ids
            if child_id in node_by_id
            and node_by_id[child_id].status not in {"completed", "failed", "skipped"}
        ]
        if pending_child_ids:
            preferred_child_id = pending_child_ids[0]
            preferred_child = node_by_id.get(preferred_child_id)
            focus_label = _parent_orchestration_focus_label(parent_node=current_node, preferred_child=preferred_child)
            normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
                protocol,
                task_id=task_id,
                agent_run_id=agent_run_id,
                work_context_stack=work_context_stack,
            )
            if normalized_protocol is None:
                normalized_protocol = protocol
            if normalized_stack is not None:
                normalized_stack = update_cursor_state(
                    normalized_stack,
                    node_id=current_node.id,
                    cursor_state=f"parent-orchestration-required:prioritize-child:{preferred_child_id}",
                )
            return normalized_protocol, normalized_stack, {
                "transition": "parent-orchestration-required",
                "requiresContinuation": True,
                "currentNodeId": (
                    normalized_protocol.work_tree.current_node_id
                    if normalized_protocol is not None and normalized_protocol.work_tree is not None
                    else current_node.id
                ),
                "nextNodeId": preferred_child_id,
                "preferredChildNodeId": preferred_child_id,
                "currentFocus": focus_label,
                "pendingChildNodeIds": pending_child_ids,
            }

    readiness_blockers: list[str] = []
    if protocol.work_tree is not None and current_node is not None and isinstance(work_tree_resolution, dict):
        raw_frontier_items = (
            work_tree_resolution.get("frontiers")
            if isinstance(work_tree_resolution.get("frontiers"), list)
            else []
        )
        frontier_items, frontier_pressure_satisfied = _frontiers_that_survive_this_turn(
            raw_frontier_items,
            evidence_refs=evidence_refs,
        )
        resolution_readiness = (
            work_tree_resolution.get("deliveryReadiness")
            if isinstance(work_tree_resolution.get("deliveryReadiness"), dict)
            else {}
        )
        resolution_blockers = [
            str(blocker)
            for blocker in resolution_readiness.get("blockers") or []
            if str(blocker).strip()
        ]
        readiness_blockers.extend(
            _delivery_blockers_that_survive_this_turn(
                resolution_blockers,
                evidence_refs=evidence_refs,
                frontier_pressure_satisfied_by_turn_evidence=frontier_pressure_satisfied,
            )
        )
        if resolution_readiness and not bool(resolution_readiness.get("ready")) and not resolution_blockers:
            readiness_blockers.append("resolution-not-ready")
        try:
            readiness = compute_delivery_readiness(
                protocol.work_tree,
                node_id=current_node.id,
                graph_state={"frontierItems": frontier_items},
            )
            readiness_blockers = [
                *readiness_blockers,
                *_delivery_blockers_that_survive_this_turn(
                    [str(blocker) for blocker in readiness.blockers],
                    evidence_refs=evidence_refs,
                    frontier_pressure_satisfied_by_turn_evidence=frontier_pressure_satisfied,
                ),
            ]
        except Exception:
            readiness_blockers = list(dict.fromkeys(readiness_blockers))
    readiness_blockers = list(dict.fromkeys(readiness_blockers))
    if readiness_blockers:
        normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
            protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            work_context_stack=work_context_stack,
        )
        return normalized_protocol or protocol, normalized_stack, {
            "transition": "work-tree-resolution-blocked",
            "requiresContinuation": True,
            "currentNodeId": (
                normalized_protocol.work_tree.current_node_id
                if normalized_protocol is not None and normalized_protocol.work_tree is not None
                else current_node.id if current_node is not None else None
            ),
            "nextNodeId": current_node.id if current_node is not None else None,
            "currentFocus": "work-tree-resolution-blocked:" + ",".join(readiness_blockers[:3]),
            "deliveryReadiness": {
                "ready": False,
                "blockers": readiness_blockers,
            },
        }
    
    # Hard gate check: if result or evidence is missing, don't complete
    if protocol is not None and protocol.verification_items:
        if not _check_delivery_hard_gates(protocol):
            return protocol, work_context_stack, {
                "transition": "delivery-gate-blocked",
                "requiresContinuation": True,
                "currentFocus": "delivery-gate-blocked",
                "blockedGates": _blocked_gate_labels(protocol),
            }

    current_node = _current_work_tree_node(protocol)
    fallback = (
        current_node.execution_summary
        if current_node is not None and current_node.execution_summary is not None
        else current_node.local_goal if current_node is not None else protocol.objective_summary
    )
    summary = _work_tree_delivery_summary(assistant_text, fallback=fallback or protocol.objective)
    return complete_current_work_node(
        protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        execution_summary=summary,
        work_context_stack=work_context_stack,
        evidence_refs=evidence_refs,
    )
def format_parent_aggregation_prompt(
    child_summaries: list[WorkContextChildCompletionSummary],
) -> str:
    """生成供父节点使用的子节点摘要聚合文本。"""
    lines: list[str] = ["## Child Node Summaries"]
    for idx, cs in enumerate(child_summaries, 1):
        status_label = "✅ Completed" if cs.status == "completed" else "❌ Failed"
        lines.append(f"\n### Child {idx}: {cs.child_node_id} [{status_label}]")
        lines.append(f"**Type**: {cs.summary_type}")
        lines.append(f"**Summary**: {cs.summary}")
        if cs.evidence_refs:
            lines.append(f"**Evidence**: {len(cs.evidence_refs)} ref(s)")
    return "\n".join(lines)
def build_takeover_continuation_request(
    base_request: dict[str, Any],
    *,
    protocol: TaskTakeoverProtocol,
    work_context_stack: WorkContextStack,
    parent_run_id: str | None = None,
    current_focus: str | None = None,
) -> dict[str, Any]:
    continuation: dict[str, Any] = {}
    for key in (
        "appId",
        "projectId",
        "spaceId",
        "branchId",
        "taskType",
        "promptProfileId",
        "seedTemplateId",
        "expectedPromptProfileId",
        "expectedSeedTemplateId",
        "currentObjective",
        "taskObjective",
        "responseRequirements",
        "resumeMessage",
        "restartMessage",
        "budget",
        "budgetState",
        "readonlyContextRef",
        "memoryWriteTagsEnabled",
        "takeoverPlanConfirmed",
        "planConfirmed",
        "confirmPlan",
        "takeoverAutoConfirm",
        "requestedBy",
        "allowModelFallback",
        "allowToolExecution",
        "candidateModels",
        "temperature",
        "maxTokens",
        "auditLevel",
        "registeredTools",
        "effectiveContextWindow",
        "windowRestartRatio",
        "windowRestartThreshold",
        "maxToolRounds",
        "maxRetainedTokens",
        "minQuality",
        "thinking",
        "reasoningEffort",
        "forcedWindowRestartBudget",
        "maxUncompressedTailBeforeDecompress",
        "selectedModel",
        "selectedProvider",
    ):
        if key in base_request:
            continuation[key] = deepcopy(base_request[key])
    current_node = _current_work_tree_node(protocol)
    continuation["takeoverProtocol"] = protocol.model_dump(by_alias=True, mode="json")
    continuation["workContextStack"] = work_context_stack.model_dump(by_alias=True, mode="json")
    continuation["currentNodeId"] = protocol.work_tree.current_node_id if protocol.work_tree is not None else None
    continuation["workingNodeAnnotation"] = current_node.working_node_annotation if current_node is not None else None
    continuation["pcMemo"] = protocol.work_tree.pc_memo if protocol.work_tree is not None else None
    continuation["topFrameId"] = work_context_stack.top_frame_id
    continuation["stackDigest"] = work_context_stack.stack_digest
    continuation["currentFocus"] = current_focus or _work_tree_focus_label(protocol)
    if parent_run_id:
        continuation["parentRunId"] = parent_run_id
    memory_retrieval_state = deepcopy(base_request.get("memoryRetrievalState")) if isinstance(base_request.get("memoryRetrievalState"), dict) else None
    if memory_retrieval_state is not None:
        memory_retrieval_state["workTreeNodeId"] = continuation["currentNodeId"]
        continuation["memoryRetrievalState"] = memory_retrieval_state

    # Package taskRuntimeState inside continuation payload
    task_runtime_state = {
        "taskId": base_request.get("taskId") or protocol.task_id,
        "phase": "task-state-loaded",
        "taskObjective": base_request.get("taskObjective") or base_request.get("currentObjective") or protocol.objective,
        "currentFocus": continuation.get("currentFocus"),
        "currentNodeId": continuation.get("currentNodeId"),
        "workingNodeAnnotation": continuation.get("workingNodeAnnotation"),
        "pcMemo": continuation.get("pcMemo"),
        "resumeMessage": base_request.get("resumeMessage"),
        "restartMessage": base_request.get("restartMessage"),
        "takeoverProtocol": continuation.get("takeoverProtocol"),
        "workContextStack": continuation.get("workContextStack"),
        "memoryRetrievalState": continuation.get("memoryRetrievalState"),
        "budgetState": base_request.get("budgetState") or base_request.get("budget"),
    }
    continuation["taskRuntimeState"] = task_runtime_state

    return continuation
def approve_takeover_completion(protocol: TaskTakeoverProtocol | None) -> TaskTakeoverProtocol | None:
    if protocol is None or protocol.work_tree is None:
        return protocol
    work_tree = protocol.work_tree
    if work_tree.status not in {"awaiting-approval", "completed"}:
        return protocol
    approved_work_tree = WorkTreeProtocol.model_validate(
        {
            **work_tree.model_dump(by_alias=True, mode="json"),
            "status": "completed",
            "currentNodeId": work_tree.root_node_id or work_tree.current_node_id,
            "updatedAt": utc_now(),
        }
    )
    return TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "completed",
            "currentPhase": "deliver",
            "workTree": approved_work_tree.model_dump(by_alias=True, mode="json"),
        }
    )
def reopen_takeover_work_node_for_revision(
    protocol: TaskTakeoverProtocol,
    *,
    task_id: str,
    agent_run_id: str,
    node_id: str | None = None,
    revision_reason: str | None = None,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
) -> tuple[TaskTakeoverProtocol, WorkContextStack]:
    if protocol.work_tree is None:
        raise ValueError("Takeover protocol does not have a work tree.")
    work_tree = protocol.work_tree
    target_node_id = node_id or work_tree.current_node_id or work_tree.root_node_id
    if target_node_id is None:
        raise ValueError("Could not determine revision target node.")
    node_by_id = _work_tree_node_index(work_tree)
    target_node = node_by_id.get(target_node_id)
    if target_node is None:
        raise KeyError(f"Unknown work-tree node: {target_node_id}")

    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == target_node.id:
            payload.update(
                {
                    "status": "in-progress",
                    "failureSummary": None,
                    "updatedAt": now,
                }
            )
        updated_nodes.append(payload)
    reopened_protocol = TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "status": "executing",
            "currentPhase": "execute",
            "workTree": {
                **work_tree.model_dump(by_alias=True, mode="json"),
                "nodes": updated_nodes,
                "status": "active",
                "currentNodeId": target_node.id,
                "activePathNodeIds": _work_tree_active_path_node_ids(work_tree, current_node_id=target_node.id),
                "pcMemo": normalize_excerpt(revision_reason or f"revision:{target_node.id}", 160),
                "updatedAt": now,
            },
        }
    )
    normalized_protocol, normalized_stack = normalize_takeover_runtime_state(
        reopened_protocol,
        task_id=task_id,
        agent_run_id=agent_run_id,
        work_context_stack=work_context_stack,
    )
    if normalized_protocol is None or normalized_stack is None:
        raise ValueError("Failed to normalize reopened work-tree state.")
    normalized_stack = update_cursor_state(
        normalized_stack,
        node_id=target_node.id,
        cursor_state=normalize_excerpt(revision_reason or "revision-requested", 96),
    )
    return normalized_protocol, normalized_stack
def persist_stack_snapshot(stack: WorkContextStack, *, task_id: str, run_id: str) -> ExternalRef:
    workspace_root = resolve_workspace_root()
    path = ensure_state_subdir("runtime/work-context-stack", workspace_root) / f"{task_id}-{run_id}.json"
    write_json(path, stack.model_dump(by_alias=True, mode="json"))
    return ExternalRef(type="file", locator=relative_workspace_path(path, workspace_root))
def load_persisted_work_context_stack(task_id: str, run_id: str) -> WorkContextStack | None:
    workspace_root = resolve_workspace_root()
    path = ensure_state_subdir("runtime/work-context-stack", workspace_root) / f"{task_id}-{run_id}.json"
    if not path.exists():
        return None
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        return None
    try:
        return WorkContextStack.model_validate(payload)
    except Exception:
        return None
def load_persisted_task_takeover_protocol(task_id: str, run_id: str) -> TaskTakeoverProtocol | None:
    workspace_root = resolve_workspace_root()
    path = ensure_state_subdir("runtime/takeover", workspace_root) / f"{task_id}-{run_id}.json"
    if not path.exists():
        return None
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        return None
    try:
        return TaskTakeoverProtocol.model_validate(payload)
    except Exception:
        return None
def _task_payload(task: Any) -> dict[str, Any]:
    return {
        "id": str(getattr(task, "id", "unknown")),
        "title": str(getattr(task, "title", "")),
        "goal": str(getattr(task, "goal", "")),
        "currentObjective": str(getattr(task, "current_objective", "") or ""),
        "currentFocus": str(getattr(task, "current_focus", "") or ""),
    }
def _trace_entries(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "moduleId": str(item.get("moduleId") or "unknown"),
            "hookName": str(item.get("hookName") or "unknown"),
            "error": str(item.get("error")) if item.get("error") is not None else None,
            "hasResult": isinstance(item.get("result"), dict),
        }
        for item in results
    ]
def _first_successful_result(results: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    applied_modules: list[str] = []
    for item in results:
        if item.get("error"):
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        if not result:
            continue
        module_id = str(item.get("moduleId") or "")
        if module_id:
            applied_modules.append(module_id)
        return result, applied_modules
    return {}, applied_modules
def _update_plan_statuses(
    plan: list[Any],
    *,
    assistant_text: str,
    tool_executions: list[dict[str, Any]],
    delivery_sections: list[TaskTakeoverDeliverySection],
) -> list[dict[str, Any]]:
    delivery_lookup = {str(section.section): section for section in delivery_sections}
    updated: list[dict[str, Any]] = []
    for step in plan:
        normalized = step.model_dump(by_alias=True, mode="json") if hasattr(step, "model_dump") else dict(step)
        phase = str(normalized.get("phase") or "")
        status = "completed"
        if phase == "execute" and not assistant_text.strip():
            status = "blocked"
        elif phase == "verify" and not tool_executions and delivery_lookup.get("evidence", TaskTakeoverDeliverySection(id="tmp", section="evidence", content="", status="missing")).status != "present":
            status = "blocked"
        elif phase == "deliver" and delivery_lookup.get("result", TaskTakeoverDeliverySection(id="tmp", section="result", content="", status="missing")).status != "present":
            status = "blocked"
        normalized["status"] = status
        updated.append(normalized)
    return updated
def build_task_takeover_protocol(
    *,
    task: Any,
    task_type: str,
    run_type: str,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
) -> TaskTakeoverProtocol | None:
    explicit_takeover = isinstance(request.get("takeoverProtocol"), dict)
    module_ids = [str(item) for item in root_mount.get("activeCapabilities") or []] or None
    payload = {
        "taskId": task.id,
        "taskType": task_type,
        "runType": run_type,
        "request": request,
        "task": _task_payload(task),
        "rootMount": root_mount,
        "currentContext": current_context,
    }
    objective_results = collect_hook_results(HookNames.TASK_TAKEOVER_PARSE_OBJECTIVE, payload, module_ids=module_ids)
    objective_result, objective_modules = _first_successful_result(objective_results)
    constraints_results = collect_hook_results(
        HookNames.TASK_TAKEOVER_EXTRACT_CONSTRAINTS,
        {**payload, "objectiveResult": objective_result},
        module_ids=module_ids,
    )
    constraints_result, constraint_modules = _first_successful_result(constraints_results)
    plan_results = collect_hook_results(
        HookNames.TASK_TAKEOVER_GENERATE_PLAN,
        {
            **payload,
            "objectiveResult": objective_result,
            "constraintsResult": constraints_result,
        },
        module_ids=module_ids,
    )
    plan_result, plan_modules = _first_successful_result(plan_results)
    if not objective_result and not constraints_result and not plan_result:
        return None

    objective = str(
        objective_result.get("objective")
        or request.get("taskObjective")
        or request.get("currentObjective")
        or getattr(task, "current_objective", None)
        or task.goal
    )
    summary = str(objective_result.get("objectiveSummary") or normalize_excerpt(objective, 160))
    protocol = TaskTakeoverProtocol(
        id=new_id("takeover", task.id, run_type, stable=True),
        taskId=task.id,
        taskType=task_type,
        runType=run_type,
        currentPhase="plan",
        status="needs-clarification" if any(item.get("required") for item in objective_result.get("ambiguities") or []) else "prepared",
        objective=objective,
        objectiveSummary=summary,
        ambiguities=objective_result.get("ambiguities") or [],
        constraints=constraints_result.get("constraints") or [],
        plan=plan_result.get("plan") or [],
        deliverySections=[],
        verificationItems=[],
        metrics=plan_result.get("metrics") or {},
        appliedModules=list(dict.fromkeys([*objective_modules, *constraint_modules, *plan_modules])),
        hookTrace=[*_trace_entries(objective_results), *_trace_entries(constraints_results), *_trace_entries(plan_results)],
    )
    protocol = enforce_takeover_confirmation_gate(protocol, request=request) or protocol
    generated_work_tree = _work_tree_from_protocol_parts(
        task_id=str(task.id),
        objective=protocol.objective,
        constraints=protocol.constraints,
        plan=protocol.plan,
        protocol_status=protocol.status,
    )
    if not explicit_takeover:
        requested_node_id = str(request.get("currentNodeId") or "").strip()
        if requested_node_id:
            node_ids = {node.id for node in generated_work_tree.nodes}
            if requested_node_id in node_ids:
                generated_work_tree = WorkTreeProtocol.model_validate(
                    {
                        **generated_work_tree.model_dump(by_alias=True, mode="json"),
                        "currentNodeId": requested_node_id,
                        "activePathNodeIds": _work_tree_active_path_node_ids(
                            generated_work_tree,
                            current_node_id=requested_node_id,
                        ),
                        "pcMemo": str(request.get("pcMemo") or f"continue:{requested_node_id}"),
                    }
                )
    protocol = protocol.model_copy(update={"work_tree": generated_work_tree})
    return protocol
def finalize_task_takeover_protocol(
    protocol: TaskTakeoverProtocol | None,
    *,
    task: Any,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    llm_result: dict[str, Any],
) -> TaskTakeoverProtocol | None:
    if protocol is None:
        return None
    if _takeover_confirmation_required(request) and not is_takeover_plan_confirmed(request):
        return enforce_takeover_confirmation_gate(protocol, request=request)
    module_ids = [str(item) for item in root_mount.get("activeCapabilities") or []] or None
    payload = {
        "taskId": task.id,
        "taskType": protocol.task_type,
        "runType": protocol.run_type,
        "request": request,
        "task": _task_payload(task),
        "rootMount": root_mount,
        "currentContext": current_context,
        "plan": [step.model_dump(by_alias=True, mode="json") for step in protocol.plan],
        "planQualityScore0_100": protocol.metrics.plan_quality_score_0_100,
        "modelOutput": str(llm_result.get("assistantText") or ""),
        "toolExecutions": [item for item in llm_result.get("toolExecutions") or [] if isinstance(item, dict)],
    }
    format_results = collect_hook_results(HookNames.TASK_TAKEOVER_FORMAT_OUTPUT, payload, module_ids=module_ids)
    formatted_result, formatted_modules = _first_successful_result(format_results)
    verify_results = collect_hook_results(HookNames.TASK_TAKEOVER_VERIFY_DELIVERY, payload, module_ids=module_ids)
    verify_result, verify_modules = _first_successful_result(verify_results)

    delivery_sections_raw = (
        verify_result.get("deliverySections")
        if isinstance(verify_result.get("deliverySections"), list)
        else formatted_result.get("deliverySections")
        if isinstance(formatted_result.get("deliverySections"), list)
        else []
    )
    verification_items_raw = verify_result.get("verificationItems") if isinstance(verify_result.get("verificationItems"), list) else []
    delivery_sections = [TaskTakeoverDeliverySection.model_validate(item) for item in delivery_sections_raw]
    verification_items = [TaskTakeoverVerificationItem.model_validate(item) for item in verification_items_raw]

    metrics_payload = protocol.metrics.model_dump(by_alias=True, mode="json")
    if isinstance(verify_result.get("metrics"), dict):
        metrics_payload.update(verify_result["metrics"])
    metrics = TaskTakeoverMetrics.model_validate(metrics_payload)
    updated_plan = _update_plan_statuses(
        protocol.plan,
        assistant_text=str(llm_result.get("assistantText") or ""),
        tool_executions=[item for item in llm_result.get("toolExecutions") or [] if isinstance(item, dict)],
        delivery_sections=delivery_sections,
    )
    completed = bool(delivery_sections) and metrics.delivery_completeness_score_0_100 == 100.0 and metrics.verification_pass_rate == 1.0
    work_tree = protocol.work_tree or _work_tree_from_protocol_parts(
        task_id=str(task.id),
        objective=protocol.objective,
        constraints=protocol.constraints,
        plan=updated_plan,
        protocol_status="completed" if completed else "verified",
    )
    work_tree = WorkTreeProtocol.model_validate(
        {
            **work_tree.model_dump(by_alias=True, mode="json"),
            "status": _work_tree_status("completed" if completed else "verified"),
            "updatedAt": utc_now(),
        }
    )
    return TaskTakeoverProtocol.model_validate(
        {
            **protocol.model_dump(by_alias=True, mode="json"),
            "currentPhase": "deliver",
            "status": "completed" if completed else "verified",
            "plan": [TaskTakeoverPlanStep.model_validate(item).model_dump(by_alias=True, mode="json") for item in updated_plan],
            "workTree": work_tree.model_dump(by_alias=True, mode="json"),
            "deliverySections": [section.model_dump(by_alias=True, mode="json") for section in delivery_sections],
            "verificationItems": [item.model_dump(by_alias=True, mode="json") for item in verification_items],
            "metrics": metrics.model_dump(by_alias=True, mode="json"),
            "appliedModules": list(dict.fromkeys([*protocol.applied_modules, *formatted_modules, *verify_modules])),
            "hookTrace": [*protocol.hook_trace, *_trace_entries(format_results), *_trace_entries(verify_results)],
        }
    )
def _work_tree_delivery_summary(text: str, *, fallback: str) -> str:
    normalized = normalize_excerpt(str(text or "").strip(), 240)
    if normalized:
        return normalized
    return normalize_excerpt(str(fallback or "Delivery completed."), 240)
def finalize_takeover_work_tree_delivery(
    protocol: TaskTakeoverProtocol | None,
    *,
    assistant_text: str,
) -> TaskTakeoverProtocol | None:
    if protocol is None or protocol.work_tree is None:
        return protocol
    updated_protocol, _, _ = advance_takeover_after_delivery(
        protocol,
        task_id=protocol.task_id,
        agent_run_id="approval-preview",
        assistant_text=assistant_text,
        work_context_stack=None,
    )
    return updated_protocol
def persist_task_takeover_protocol(protocol: TaskTakeoverProtocol, *, task_id: str, run_id: str) -> ExternalRef:
    workspace_root = resolve_workspace_root()
    path = ensure_state_subdir("runtime/takeover", workspace_root) / f"{task_id}-{run_id}.json"
    write_json(path, protocol.model_dump(by_alias=True, mode="json"))
    return ExternalRef(type="file", locator=relative_workspace_path(path, workspace_root))
def summarize_task_takeover_protocol(protocol: TaskTakeoverProtocol) -> str:
    lines = [
        f"Takeover objective: {protocol.objective_summary}",
        f"Plan steps: {len(protocol.plan)}",
        f"Plan quality: {protocol.metrics.plan_quality_score_0_100}",
        f"Verification pass rate: {protocol.metrics.verification_pass_rate}",
        f"Delivery completeness: {protocol.metrics.delivery_completeness_score_0_100}",
        f"Rework count: {protocol.metrics.rework_count}",
    ]
    if protocol.applied_modules:
        lines.append("Applied takeover modules: " + ", ".join(protocol.applied_modules))
    return "\n".join(lines)
def _fallback_work_tree_node(nodes: list[WorkTreeNode]) -> WorkTreeNode | None:
    if not nodes:
        return None
    executable_nodes = [
        node
        for node in nodes
        if not (len(nodes) > 1 and node.parent_node_id is None and node.child_node_ids)
    ]
    if not executable_nodes:
        executable_nodes = nodes
    for preferred_status in ("in-progress", "blocked", "pending"):
        candidate = next((node for node in executable_nodes if node.status == preferred_status), None)
        if candidate is not None:
            return candidate
    candidate = next((node for node in executable_nodes if node.status not in {"completed", "skipped"}), None)
    if candidate is not None:
        return candidate
    return executable_nodes[-1]
def restore_takeover_work_tree_pointer(candidate: dict[str, Any]) -> dict[str, Any]:
    """Restore a durable work-tree pointer for resume request state.

    Priority:
    1) keep existing currentNodeId when valid,
    2) fallback to the nearest executable node,
    3) align recoveryAnchor and workTree status.
    """
    if not isinstance(candidate, dict):
        return {}
    try:
        protocol = TaskTakeoverProtocol.model_validate(candidate)
    except Exception:
        return candidate

    work_tree = protocol.work_tree
    if work_tree is None:
        return protocol.model_dump(by_alias=True, mode="json")

    node_by_id = {node.id: node for node in work_tree.nodes}
    current_node = node_by_id.get(str(work_tree.current_node_id)) if work_tree.current_node_id is not None else None
    if current_node is None:
        current_node = _fallback_work_tree_node(work_tree.nodes)

    recovered_status = work_tree.status
    if recovered_status == "planned" and current_node is not None:
        recovered_status = "active"

    repaired_payload = protocol.model_dump(by_alias=True, mode="json")
    repaired_payload["workTree"] = {
        **repaired_payload.get("workTree", {}),
        "currentNodeId": current_node.id if current_node is not None else None,
        "recoveryAnchor": (
            current_node.recovery_anchor
            if current_node is not None and current_node.recovery_anchor is not None
            else work_tree.recovery_anchor
        ),
        "status": recovered_status,
    }
    repaired_protocol = TaskTakeoverProtocol.model_validate(repaired_payload)
    return repaired_protocol.model_dump(by_alias=True, mode="json")
__all__ = [name for name in globals() if not name.startswith("__")]
