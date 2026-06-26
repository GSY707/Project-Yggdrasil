from __future__ import annotations

from .takeover_work_tree_runtime import *  # noqa: F403,F401

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
            payload.update(
                {
                    "status": "completed",
                    "executionSummary": summary,
                    "failureSummary": None,
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


def advance_takeover_after_delivery(
    protocol: TaskTakeoverProtocol | None,
    *,
    task_id: str,
    agent_run_id: str,
    assistant_text: str,
    work_context_stack: WorkContextStack | dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
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

    if protocol is not None and protocol.verification_items:
        if not _check_delivery_hard_gates(protocol):
            return protocol, work_context_stack, {
                "transition": "delivery-gate-blocked",
                "requiresContinuation": False,
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
    if not is_takeover_plan_confirmed(request):
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
