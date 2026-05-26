from ._common import *  # noqa: F403,F401
from ..tool_runtime import resolve_registered_tool_descriptors

def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000.0, 2)

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


def _root_branches(
    identity_refs: list[EntityRef],
    context_refs: list[EntityRef],
    execution_refs: list[EntityRef],
) -> dict[str, str | None]:
    return {
        "identity": identity_refs[0].id if identity_refs else None,
        "context": context_refs[0].id if context_refs else None,
        "execution": execution_refs[0].id if execution_refs else None,
    }


def _normalized_optional_text(value: Any) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _work_context_top_node_id(work_context_stack: Any) -> str | None:
    if not isinstance(work_context_stack, dict):
        return None
    top_frame_id = _normalized_optional_text(
        work_context_stack.get("topFrameId") or work_context_stack.get("top_frame_id")
    )
    frames = work_context_stack.get("frames") if isinstance(work_context_stack.get("frames"), list) else []
    if top_frame_id is not None:
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            if _normalized_optional_text(frame.get("id")) == top_frame_id:
                return _normalized_optional_text(frame.get("nodeId") or frame.get("node_id"))
    for frame in frames:
        if not isinstance(frame, dict):
            continue
        if str(frame.get("status") or "").strip() == "active":
            return _normalized_optional_text(frame.get("nodeId") or frame.get("node_id"))
    return None


def _runtime_pointer_fields(payload: dict[str, Any] | None) -> dict[str, str | None]:
    request = payload or {}
    takeover_protocol = request.get("takeoverProtocol") if isinstance(request.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else {}
    work_context_stack = request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else {}

    current_node_id = (
        _normalized_optional_text(request.get("currentNodeId"))
        or _normalized_optional_text(work_tree.get("currentNodeId"))
        or _normalized_optional_text(request.get("workTreeNodeId"))
        or _normalized_optional_text(memory_retrieval_state.get("workTreeNodeId"))
        or _work_context_top_node_id(work_context_stack)
    )
    working_node_annotation = (
        _normalized_optional_text(request.get("workingNodeAnnotation"))
        or _normalized_optional_text(work_tree.get("workingNodeAnnotation"))
        or (f"<Working_Node: {current_node_id}>" if current_node_id is not None else "<Working_Node: standby>")
    )
    pc_memo = _normalized_optional_text(request.get("pcMemo")) or _normalized_optional_text(work_tree.get("pcMemo"))
    top_frame_id = (
        _normalized_optional_text(request.get("topFrameId"))
        or _normalized_optional_text(work_context_stack.get("topFrameId") or work_context_stack.get("top_frame_id"))
    )
    stack_digest = (
        _normalized_optional_text(request.get("stackDigest"))
        or _normalized_optional_text(work_context_stack.get("stackDigest") or work_context_stack.get("stack_digest"))
    )
    return {
        "currentNodeId": current_node_id,
        "workingNodeAnnotation": working_node_annotation,
        "pcMemo": pc_memo,
        "topFrameId": top_frame_id,
        "stackDigest": stack_digest,
    }


def _resolve_startup_state(
    payload: dict[str, Any] | None,
    *,
    task_objective: Any = None,
    current_focus: Any = None,
    mounted_context_count: int = 0,
) -> dict[str, str | None]:
    pointer_fields = _runtime_pointer_fields(payload)
    has_work = any(
        _normalized_optional_text(value) is not None
        for value in (
            (payload or {}).get("taskObjective") if isinstance(payload, dict) else None,
            (payload or {}).get("currentObjective") if isinstance(payload, dict) else None,
            task_objective,
            current_focus,
        )
    ) or mounted_context_count > 0
    startup_mode = "resume-node" if pointer_fields["currentNodeId"] is not None else "bootstrap" if has_work else "standby"
    standby_reason = None if startup_mode != "standby" else "no-active-work"
    return {
        **pointer_fields,
        "startupMode": startup_mode,
        "standbyReason": standby_reason,
    }


def _registered_tool_index(active_capabilities: list[str], strip_body: bool = False) -> list[dict[str, Any]]:
    descriptors = resolve_registered_tool_descriptors(active_capabilities)
    results = []
    for descriptor in descriptors:
        dump = descriptor.model_dump(by_alias=True, mode="json")
        if strip_body:
            for key in ["inputSchema", "implementationRef", "timeoutMs", "permissionRequired"]:
                dump.pop(key, None)
        results.append(dump)
    return results


def _capability_index(active_capabilities: list[str]) -> list[dict[str, str]]:
    return [
        {
            "id": module_id,
            "label": module_id,
            "kind": "capability",
            "protocol": "module-hook",
        }
        for module_id in active_capabilities
    ]


def _mailbox_state(payload: dict[str, Any] | None, persisted_state: dict[str, Any] | None = None) -> dict[str, Any]:
    mailbox = payload.get("mailboxState") if isinstance((payload or {}).get("mailboxState"), dict) else {}
    source = persisted_state if isinstance(persisted_state, dict) else mailbox
    try:
        pending_count = max(int(source.get("pendingCount") or 0), 0)
    except (TypeError, ValueError):
        pending_count = 0
    return {
        "status": _normalized_optional_text(source.get("status")) or ("pending" if pending_count > 0 else "idle"),
        "pendingCount": pending_count,
        "wakeOnMessage": bool(source.get("wakeOnMessage", mailbox.get("wakeOnMessage", True))),
    }


def _startup_load_order() -> list[str]:
    return ["你的能力", "你的工具", "你的工作", "你的知识"]


def _semantic_roots(
    identity_refs: list[EntityRef],
    context_refs: list[EntityRef],
    execution_refs: list[EntityRef],
    startup_state: dict[str, str | None],
    is_world_level: bool = True,
) -> dict[str, dict[str, Any]]:
    execution_summary = "通用工作协议、待机入口、工作状态读取入口。" if is_world_level else "工作树、当前工作节点、留言、任务预算和待机队列。"
    exec_root = {
        "label": "[ID: 003 我要干什么]",
        "rootBranch": "execution",
        "primaryRefId": execution_refs[0].id if execution_refs else None,
        "summary": execution_summary,
    }
    if not is_world_level:
        exec_root["currentNodeId"] = startup_state.get("currentNodeId")
        exec_root["workingNodeAnnotation"] = startup_state.get("workingNodeAnnotation")
        
    return {
        "identity": {
            "label": "[ID: 001 我是谁]",
            "rootBranch": "identity",
            "primaryRefId": identity_refs[0].id if identity_refs else None,
            "summary": "人格、权限、能力、工具使用偏好、长期自我约束。",
        },
        "context": {
            "label": "[ID: 002 我在哪]",
            "rootBranch": "context",
            "primaryRefId": context_refs[0].id if context_refs else None,
            "summary": "项目、世界、环境、来源边界和当前外部状态。",
        },
        "execution": exec_root,
    }


def _system_root_protocol(
    capability_index: list[dict[str, Any]],
    tool_index: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "nodeId": "SYS_ROOT_PROTOCOL",
        "label": "[NODE_ID: SYS_ROOT_PROTOCOL]",
        "summary": "系统宪法、底层协议和能力索引入口。",
        "protocols": ["Agent Runtime v0.2", "WorkTreeProtocol v0.2"],
        "capabilityCount": len(capability_index),
        "toolCount": len(tool_index),
    }


def _standby_state(
    startup_state: dict[str, str | None],
    mailbox_state: dict[str, Any],
) -> dict[str, Any]:
    is_standby = startup_state.get("startupMode") == "standby"
    pending_count = int(mailbox_state.get("pendingCount") or 0)
    standby_reason = startup_state.get("standbyReason")
    if is_standby and pending_count > 0:
        standby_reason = "mailbox-pending"
    return {
        "isStandby": is_standby,
        "reason": standby_reason,
        "pendingMailboxCount": pending_count,
    }


def _root_mount_runtime_metadata(
    payload: dict[str, Any] | None,
    *,
    task_objective: Any,
    current_focus: Any,
    identity_refs: list[EntityRef],
    context_refs: list[EntityRef],
    execution_refs: list[EntityRef],
    active_capabilities: list[str],
    mailbox_state: dict[str, Any] | None = None,
    is_world_level: bool = True,
) -> dict[str, Any]:
    startup_state = _resolve_startup_state(payload, task_objective=task_objective, current_focus=current_focus)
    if is_world_level:
        startup_state["currentNodeId"] = None
        startup_state["workingNodeAnnotation"] = None
        startup_state["pcMemo"] = None
        startup_state["topFrameId"] = None
        startup_state["stackDigest"] = None
        
    capability_index = _capability_index(active_capabilities)
    tool_index = _registered_tool_index(active_capabilities, strip_body=is_world_level)
    mailbox_state = _mailbox_state(payload, mailbox_state)
    return {
        "semanticRoots": _semantic_roots(identity_refs, context_refs, execution_refs, startup_state, is_world_level),
        "systemRootProtocol": _system_root_protocol(capability_index, tool_index),
        "capabilityIndex": capability_index,
        "toolIndex": tool_index,
        "startupLoadOrder": _startup_load_order(),
        "startupMode": startup_state["startupMode"],
        "mailboxState": mailbox_state,
        "standbyState": _standby_state(startup_state, mailbox_state),
        "currentNodeId": startup_state["currentNodeId"],
        "workingNodeAnnotation": startup_state["workingNodeAnnotation"],
        "pcMemo": startup_state["pcMemo"],
        "topFrameId": startup_state["topFrameId"],
        "stackDigest": startup_state["stackDigest"],
    }


def _startup_contract(payload: dict[str, Any], *, task_record: Any | None = None) -> dict[str, str]:
    response_requirements = payload.get("responseRequirements")
    restart_message = payload.get("restartMessage")
    if restart_message is None and task_record is not None:
        restart_message = getattr(task_record, "restart_message", None)
    if restart_message is None:
        restart_message = payload.get("resumeMessage")

    contract: dict[str, str] = {}
    if response_requirements is not None and str(response_requirements).strip():
        contract["responseRequirements"] = str(response_requirements)
    if restart_message is not None and str(restart_message).strip():
        contract["restartMessage"] = str(restart_message)
    return contract

def _active_capabilities() -> list[str]:
    return active_module_ids()

def _load_active_module(module_id: str):
    return load_active_module(module_id)

def _call_module_hook(module_id: str, hook_name: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    return call_module_hook(module_id, hook_name, payload)

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
    if any(term in text for term in ("writing", "write", "写作", "叙事", "剧情", "章节", "角色", "设定", "trpg")):
        return "writing"
    if any(term in text for term in ("maintenance", "维护", "修复", "回归")):
        return "maintenance"
    return "generic"

def _estimate_context_tokens(current_context: list[dict[str, Any]], *, limit: int = 10) -> int:
    total = 0
    for index, item in enumerate(current_context[:limit], start=1):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("kind") or f"context-{index}")
        raw_content = str(item.get("content") or item)
        content = raw_content if bool(item.get("verbatim")) else normalize_excerpt(raw_content, 240)
        total += max(1, len(f"{title} {content}".strip()) // 4)
    return total

def _estimate_usage(task, root_mount: dict[str, Any], current_context: list[dict[str, Any]], payload: dict[str, Any]) -> tuple[int, int]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    if usage.get("inputTokens") is not None or usage.get("outputTokens") is not None:
        return int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0))

    source_text = " ".join(
        str(value)
        for value in [
            normalize_excerpt(task.goal or "", 240),
            normalize_excerpt(task.current_objective or "", 240),
            normalize_excerpt(task.current_focus or "", 160),
            normalize_excerpt(str(root_mount.get("rootSummary") or ""), 240),
        ]
        if value is not None and str(value).strip()
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


def _enforce_consumed_budget(budget: BudgetState, *, input_tokens: int, output_tokens: int, cost_used: float) -> None:
    consumed_total_tokens = input_tokens + output_tokens
    if budget.token_budget_total is not None and budget.token_budget_used + consumed_total_tokens > budget.token_budget_total:
        raise ValueError("Token budget exceeded after model invocation.")
    if budget.cost_budget_total is not None and budget.cost_budget_used + cost_used > budget.cost_budget_total:
        raise ValueError("Cost budget exceeded after model invocation.")

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
    mailbox_state: dict[str, Any] | None = None
    mailbox_messages: list[dict[str, Any]] = []
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
            runtime_repository = RuntimeRepository(session)
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
                mailbox_state = runtime_repository.get_mailbox_state(task_record.id)
                mailbox_messages = [
                    message.model_dump(by_alias=True, mode="json")
                    for message in runtime_repository.list_mailbox_messages(task_id=task_record.id, status="pending", limit=16)
                ]
    except Exception:
        task_record = None

    app_id = resolve_runtime_application_id(
        task_record.app_id if task_record is not None else request.get("appId"),
    )
    active_capabilities = resolve_application_active_capabilities(
        app_id=app_id,
        requested_capabilities=request.get("activeCapabilities") if isinstance(request.get("activeCapabilities"), list) else None,
    )
    host_space_id = task_record.space_id if task_record is not None else str(request.get("spaceId", DEFAULT_SPACE_ID))
    runtime_metadata = _root_mount_runtime_metadata(
        request,
        task_objective=task_objective,
        current_focus=current_focus,
        identity_refs=identity_refs,
        context_refs=context_refs,
        execution_refs=execution_refs,
        active_capabilities=active_capabilities,
        mailbox_state=mailbox_state,
        is_world_level=True,
    )

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
    summary_parts.append(f"Startup mode: {runtime_metadata['startupMode']}.")
    if int(runtime_metadata["mailboxState"].get("pendingCount") or 0) > 0:
        summary_parts.append(f"Mailbox pending messages: {runtime_metadata['mailboxState']['pendingCount']}.")
    if runtime_metadata.get("currentNodeId") is not None:
        summary_parts.append(f"Current work node: {runtime_metadata['currentNodeId']}")
    if runtime_metadata["startupMode"] == "standby":
        summary_parts.append("No active work is mounted; remain in standby until user or mailbox input arrives.")

    module_mount_fragments: list[dict[str, Any]] = []
    module_mounted_node_refs: list[dict[str, Any]] = []
    accessible_mounts: list[dict[str, Any]] = []
    startup_contract = _startup_contract(request, task_record=task_record)
    startup_results = collect_hook_results(
        HookNames.AGENT_STARTUP_MOUNT_ROOT,
        {
            "taskId": task_id,
            "projectId": project_id,
            "spaceId": host_space_id,
            "branchId": branch_id,
            "ownerProfileId": task_record.owner_profile_id if task_record is not None else request.get("ownerProfileId"),
            "subject": (
                f"profile:{task_record.owner_profile_id}"
                if task_record is not None and task_record.owner_profile_id
                else request.get("subject")
            ),
            "rootBranches": {
                "identity": [reference.model_dump(mode="json") for reference in identity_refs],
                "context": [reference.model_dump(mode="json") for reference in context_refs],
                "execution": [reference.model_dump(mode="json") for reference in execution_refs],
            },
            "startupPolicy": {
                "includeMountedSpaces": True,
                "mode": "runtime-root-mount",
            },
            "activeCapabilities": active_capabilities,
        },
        module_ids=active_capabilities,
    )
    for item in startup_results:
        if item.get("error"):
            continue
        result = item.get("result") if isinstance(item.get("result"), dict) else {}
        if result.get("summary") is not None:
            summary_parts.append(normalize_excerpt(str(result["summary"]), 180))
        for summary_part in result.get("rootSummaryParts") or []:
            if summary_part is not None:
                summary_parts.append(normalize_excerpt(str(summary_part), 180))
        module_mount_fragments.extend(fragment for fragment in result.get("mountFragments") or [] if isinstance(fragment, dict))
        module_mounted_node_refs.extend(reference for reference in result.get("mountedNodeRefs") or [] if isinstance(reference, dict))
        accessible_mounts.extend(mount for mount in result.get("accessibleMounts") or [] if isinstance(mount, dict))

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
        semanticRoots=runtime_metadata["semanticRoots"],
        systemRootProtocol=runtime_metadata["systemRootProtocol"],
        capabilityIndex=runtime_metadata["capabilityIndex"],
        toolIndex=runtime_metadata["toolIndex"],
        startupLoadOrder=runtime_metadata["startupLoadOrder"],
        startupMode=runtime_metadata["startupMode"],
        mailboxState=runtime_metadata["mailboxState"],
        standbyState=runtime_metadata["standbyState"],
        currentNodeId=runtime_metadata["currentNodeId"],
        workingNodeAnnotation=runtime_metadata["workingNodeAnnotation"],
        pcMemo=runtime_metadata["pcMemo"],
        topFrameId=runtime_metadata["topFrameId"],
        stackDigest=runtime_metadata["stackDigest"],
        generatedAt=utc_now(),
    )
    response = package.model_dump(by_alias=True, mode="json")
    response["mountedNodeRefs"] = []
    seen_mounted_refs: set[str] = set()
    for reference in [
        *response["identityRefs"],
        *response["contextRefs"],
        *response["executionRefs"],
        *module_mounted_node_refs,
    ]:
        ref_key = f"{reference.get('kind')}::{reference.get('id')}"
        if ref_key in seen_mounted_refs:
            continue
        seen_mounted_refs.add(ref_key)
        response["mountedNodeRefs"].append(reference)
    response["spaceId"] = host_space_id
    response["source"] = "database" if task_record is not None else "preview"
    response["moduleMountFragments"] = module_mount_fragments
    response["accessibleMounts"] = accessible_mounts
    response["mailboxMessages"] = mailbox_messages
    response["rootBranches"] = _root_branches(identity_refs, context_refs, execution_refs)
    response["startupContract"] = startup_contract
    response["cached"] = _cache_package_entry(coordinator, f"runtime/tasks/{task_id}/root-mount/current", response)
    return response


def build_task_runtime_state(
    task_id: str,
    payload: dict[str, Any] | None = None,
    *,
    phase: Literal["start-state", "task-state-loaded", "lossless-restore"] | None = None,
) -> TaskRuntimeState:
    request = payload or {}
    runtime = get_persistence_runtime()
    task_record = None
    
    current_focus = request.get("currentFocus")
    task_objective = request.get("taskObjective") or request.get("currentObjective")
    resume_message = request.get("resumeMessage")
    restart_message = request.get("restartMessage")
    
    try:
        with runtime.session_scope() as session:
            task_repository = TaskRepository(session)
            task_record = task_repository.get_task(task_id)
            if task_record is not None:
                current_focus = request.get("currentFocus") or task_record.current_focus
                task_objective = request.get("taskObjective") or request.get("currentObjective") or task_record.current_objective or task_record.goal
                resume_message = request.get("resumeMessage") or task_record.resume_message
                restart_message = request.get("restartMessage") or task_record.restart_message
                if task_record.active_snapshot_id and not resume_message:
                    snapshot = task_repository.get_snapshot(task_record.active_snapshot_id)
                    if snapshot is not None and snapshot.resume_message:
                        resume_message = snapshot.resume_message
    except Exception:
        pass

    pointer_fields = _runtime_pointer_fields(request)
    
    takeover_protocol_raw = request.get("takeoverProtocol")
    takeover_protocol = None
    if isinstance(takeover_protocol_raw, dict):
        try:
            takeover_protocol = TaskTakeoverProtocol.model_validate(takeover_protocol_raw)
        except Exception:
            pass
    elif isinstance(takeover_protocol_raw, TaskTakeoverProtocol):
        takeover_protocol = takeover_protocol_raw
        
    work_context_stack_raw = request.get("workContextStack")
    work_context_stack = None
    if isinstance(work_context_stack_raw, dict):
        try:
            work_context_stack = WorkContextStack.model_validate(work_context_stack_raw)
        except Exception:
            pass
    elif isinstance(work_context_stack_raw, WorkContextStack):
        work_context_stack = work_context_stack_raw

    budget_state = _normalize_budget(request)
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else None

    if phase is None:
        if request.get("resumeToken") is not None or request.get("resumeMessage") is not None or request.get("restartMessage") is not None:
            phase = "lossless-restore"
        elif pointer_fields["currentNodeId"] is not None:
            phase = "task-state-loaded"
        else:
            phase = "start-state"

    return TaskRuntimeState(
        taskId=task_id,
        phase=phase,
        taskObjective=str(task_objective) if task_objective is not None else None,
        currentFocus=str(current_focus) if current_focus is not None else None,
        currentNodeId=pointer_fields["currentNodeId"],
        workingNodeAnnotation=pointer_fields["workingNodeAnnotation"],
        pcMemo=pointer_fields["pcMemo"],
        resumeMessage=str(resume_message) if resume_message is not None else None,
        restartMessage=str(restart_message) if restart_message is not None else None,
        takeoverProtocol=takeover_protocol,
        workContextStack=work_context_stack,
        memoryRetrievalState=memory_retrieval_state,
        budgetState=budget_state,
    )


__all__ = [name for name in globals() if not name.startswith('__')]

