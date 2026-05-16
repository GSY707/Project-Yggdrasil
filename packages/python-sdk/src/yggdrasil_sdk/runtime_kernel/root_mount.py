from ._common import *  # noqa: F403,F401

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

    app_id = resolve_runtime_application_id(
        task_record.app_id if task_record is not None else request.get("appId"),
    )
    active_capabilities = resolve_application_active_capabilities(
        app_id=app_id,
        requested_capabilities=request.get("activeCapabilities") if isinstance(request.get("activeCapabilities"), list) else None,
    )
    host_space_id = task_record.space_id if task_record is not None else str(request.get("spaceId", DEFAULT_SPACE_ID))

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

    module_mount_fragments: list[dict[str, Any]] = []
    module_mounted_node_refs: list[dict[str, Any]] = []
    accessible_mounts: list[dict[str, Any]] = []
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
    response["cached"] = _cache_package_entry(coordinator, f"runtime/tasks/{task_id}/root-mount/current", response)
    return response



__all__ = [name for name in globals() if not name.startswith('__')]

