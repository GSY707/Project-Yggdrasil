from __future__ import annotations

from typing import Any

from ._common import *  # noqa: F403,F401
from ..contracts import TaskTakeoverDeliverySection, TaskTakeoverMetrics, TaskTakeoverPlanStep, TaskTakeoverVerificationItem, WorkTreeNode, WorkTreeProtocol


_WORK_TREE_PHASE_MAP = {
    "objective": "planning",
    "constraints": "planning",
    "plan": "planning",
    "execute": "executing",
    "verify": "verification",
    "deliver": "delivery",
}


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
        rootObjective=objective,
        status=_work_tree_status(protocol_status),
        currentNodeId=current_node.id if current_node is not None else None,
        nodes=nodes,
        recoveryAnchor=current_node.recovery_anchor if current_node is not None else None,
        entropyBudgetRemaining=entropy_budget_remaining,
    )


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
    protocol = protocol.model_copy(
        update={
            "work_tree": _work_tree_from_protocol_parts(
                task_id=str(task.id),
                objective=protocol.objective,
                constraints=protocol.constraints,
                plan=protocol.plan,
                protocol_status=protocol.status,
            )
        }
    )
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
    return protocol.model_copy(
        update={
            "currentPhase": "deliver",
            "status": "completed" if completed else "verified",
            "plan": [TaskTakeoverPlanStep.model_validate(item) for item in updated_plan],
            "work_tree": _work_tree_from_protocol_parts(
                task_id=str(task.id),
                objective=protocol.objective,
                constraints=protocol.constraints,
                plan=updated_plan,
                protocol_status="completed" if completed else "verified",
            ),
            "deliverySections": delivery_sections,
            "verificationItems": verification_items,
            "metrics": metrics,
            "appliedModules": list(dict.fromkeys([*protocol.applied_modules, *formatted_modules, *verify_modules])),
            "hookTrace": [*protocol.hook_trace, *_trace_entries(format_results), *_trace_entries(verify_results)],
        }
    )


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
    for preferred_status in ("in-progress", "blocked", "pending"):
        candidate = next((node for node in nodes if node.status == preferred_status), None)
        if candidate is not None:
            return candidate
    candidate = next((node for node in nodes if node.status not in {"completed", "skipped"}), None)
    if candidate is not None:
        return candidate
    return nodes[-1]


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

    repaired_work_tree = work_tree.model_copy(
        update={
            "current_node_id": current_node.id if current_node is not None else None,
            "recovery_anchor": (
                current_node.recovery_anchor
                if current_node is not None and current_node.recovery_anchor is not None
                else work_tree.recovery_anchor
            ),
            "status": recovered_status,
        }
    )
    repaired_protocol = protocol.model_copy(update={"work_tree": repaired_work_tree})
    return repaired_protocol.model_dump(by_alias=True, mode="json")


__all__ = [name for name in globals() if not name.startswith("__")]