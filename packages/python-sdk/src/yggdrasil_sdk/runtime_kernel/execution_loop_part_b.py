from .execution_loop_part_a import *  # noqa: F401,F403
from .execution_loop_transitions import _finalize_execution_transition, _handle_window_restart_transition
from .root_mount import _elapsed_ms, _infer_task_type

def _retrieve_context_from_memory_tree(
    session,
    *,
    task,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    execution_root_id: str,
) -> dict[str, Any]:
    runtime_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    window_index = max(_int_metric(runtime_metrics.get("windowIndex"), _int_metric(request.get("windowIndex"), 1)), 1)
    work_tree_node_id = _work_tree_node_id_from_request(request)
    materialized_node_ids = _materialize_runtime_context_items(
        session,
        task=task,
        current_context=current_context,
        root_mount=root_mount,
        execution_root_id=execution_root_id,
        window_index=window_index,
        source_work_tree_node_id=work_tree_node_id,
        source_run_id=(
            str(request.get("agentRunId") or "").strip()
            or str(request.get("parentRunId") or "").strip()
            or None
        ),
    )

    repository = NodeRepository(session)
    memory_repository = MemoryRepository(session)
    nodes = [
        node.model_dump(by_alias=True, mode="json")
        for node in repository.list_nodes(branch_id=task.branch_id, limit=2000)
        if node.node_type != "root"
    ]
    edges = [edge.model_dump(by_alias=True, mode="json") for edge in repository.list_edges(branch_id=task.branch_id, limit=4000)]
    annotations = [
        annotation.model_dump(by_alias=True, mode="json")
        for annotation in repository.list_source_annotations(branch_id=task.branch_id, limit=4000)
    ]

    active_capabilities = [str(item) for item in root_mount.get("activeCapabilities") or []]
    execution_context = {
        "projectId": task.project_id,
        "spaceId": task.space_id,
        "branchId": task.branch_id,
        "ownerProfileId": task.owner_profile_id,
        "subject": request.get("subject") or (f"profile:{task.owner_profile_id}" if task.owner_profile_id else None),
        "rootMount": root_mount,
    }
    expansion_summaries: list[str] = []
    expansion_module_ids = [module_id for module_id in active_capabilities if module_id != "text-memory"] or None
    if expansion_module_ids:
        for item in collect_hook_results(
            HookNames.MEMORY_RETRIEVE_EXPAND,
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "ownerProfileId": task.owner_profile_id,
                "subject": execution_context["subject"],
                "executionContext": execution_context,
            },
            module_ids=expansion_module_ids,
        ):
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            nodes.extend(node for node in result.get("nodes") or [] if isinstance(node, dict))
            edges.extend(edge for edge in result.get("edges") or [] if isinstance(edge, dict))
            annotations.extend(annotation for annotation in result.get("sourceAnnotations") or [] if isinstance(annotation, dict))
            if result.get("summary") is not None:
                expansion_summaries.append(str(result["summary"]))

    retrieval_query = " ".join(
        part.strip()
        for part in [
            str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal or ""),
            str(request.get("currentFocus") or task.current_focus or ""),
            str(request.get("resumeMessage") or root_mount.get("resumeMessage") or ""),
        ]
        if part and part.strip()
    )
    retrieval_request = {
        "id": new_id("retr", task.id, utc_now().isoformat()),
        "projectId": task.project_id,
        "spaceId": task.space_id,
        "branchId": task.branch_id,
        "queryText": retrieval_query,
        "seedNodeRefs": [
            *[dict(reference) for reference in root_mount.get("identityRefs") or [] if isinstance(reference, dict)],
            *[dict(reference) for reference in root_mount.get("contextRefs") or [] if isinstance(reference, dict)],
            *[dict(reference) for reference in root_mount.get("executionRefs") or [] if isinstance(reference, dict)],
            *[{"kind": "node", "id": node_id} for node_id in materialized_node_ids],
        ],
        "traversalStart": "mixed",
        "expansionMode": "parallel",
        "readDepth": 2,
        "lateralHops": 1,
        "maxRelatedNodes": 6,
        "maxLeafNodes": 6,
        "precisionMode": "balanced",
        "includeNaturalLanguageSummary": True,
        "includeChildNames": True,
        "includeRelatedNames": True,
        "reverseTraceMode": bool(request.get("memoryReverseTraceMode", work_tree_node_id is not None)),
        "workTreeNodeId": work_tree_node_id,
        "windowIndex": window_index,
        "tokenBudget": request.get("maxRetainedTokens"),
        "createdAt": utc_now().isoformat(),
    }
    retrieval_request_record = memory_repository.create_retrieval_request(retrieval_request)
    retrieval_request = retrieval_request_record.model_dump(by_alias=True, mode="json")
    retrieval_bundle = call_module_hook(
        "text-memory",
        HookNames.MEMORY_RETRIEVE_EXPAND,
        {
            "retrievalRequest": retrieval_request,
            "nodes": _dedupe_memory_records(nodes),
            "edges": _dedupe_memory_records(edges),
            "sourceAnnotations": _dedupe_memory_records(annotations),
            "executionContext": execution_context,
        },
    )
    if retrieval_bundle is None:
        return {
            "contextItems": current_context,
            "protectedItems": [],
            "summary": None,
            "materializedNodeIds": materialized_node_ids,
            "retrievalRequest": retrieval_request,
        }

    node_payloads = [item for item in retrieval_bundle.get("nodePayloads") or [] if isinstance(item, dict)]
    matched_refs = [item for item in retrieval_bundle.get("matchedNodeRefs") or [] if isinstance(item, dict)]
    context_items: list[dict[str, Any]] = []
    summary_parts = [str(retrieval_bundle.get("naturalLanguageSummary") or "").strip(), *[summary.strip() for summary in expansion_summaries if summary.strip()]]
    if materialized_node_ids:
        summary_parts.append(f"Materialized {len(materialized_node_ids)} runtime context items into the memory tree before retrieval.")
    summary_text = " ".join(part for part in summary_parts if part)
    if summary_text:
        context_items.append(
            {
                "id": new_id("retrieval-summary", task.id, retrieval_request["id"], stable=True),
                "kind": "retrieval-summary",
                "title": "Memory retrieval summary",
                "content": normalize_excerpt(summary_text, 480),
                "rootBranch": "context",
            }
        )
    context_items.extend(_context_item_from_retrieved_node(item) for item in node_payloads)
    if _should_trim_retrieved_context(current_context):
        context_items = _trim_context_items_to_token_budget(context_items, _memory_retrieval_token_budget(request))
    retained_node_ids = {
        str((item.get("ref") or {}).get("id") or "")
        for item in context_items
        if isinstance(item, dict) and isinstance(item.get("ref"), dict) and item.get("ref", {}).get("id")
    }
    if retained_node_ids:
        matched_refs = [reference for reference in matched_refs if str(reference.get("id") or "") in retained_node_ids]
    else:
        matched_refs = []
    return {
        "contextItems": context_items or current_context,
        "protectedItems": matched_refs,
        "summary": summary_text or None,
        "materializedNodeIds": materialized_node_ids,
        "retrievalRequest": retrieval_request,
        "retrievalBundle": retrieval_bundle,
    }

def execute_main_agent_work_item(work_item: dict[str, Any]) -> dict[str, object]:
    task_id = str(work_item.get("taskId"))
    request = work_item.get("payload") if isinstance(work_item.get("payload"), dict) else {}
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    runtime_timings: dict[str, Any] = {}
    work_started_at = perf_counter()
    lock_owner = new_id("worker", task_id, utc_now().isoformat())
    if not coordinator.acquire_lock(f"task:{task_id}", lock_owner, ttl_seconds=120):
        return {"status": "locked", "taskId": task_id}

    try:
        with runtime.session_scope() as session:
            task_load_started_at = perf_counter()
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
            if snapshot is not None and command == "resume":
                for pending_action in snapshot.pending_actions or []:
                    if not isinstance(pending_action, dict):
                        continue
                    if pending_action.get("kind") not in {"pending-tool-calls", "window-restart"}:
                        continue
                    if pending_action.get("kind") == "pending-tool-calls" or pending_action.get("checksum") is not None:
                        integrity_ok, integrity_error = _verify_snapshot_integrity(pending_action)
                        if not integrity_ok:
                            task_repository.update_snapshot(
                                snapshot.id,
                                status="created",
                                blockers=[f"snapshot-corrupted:{integrity_error or 'unknown'}"],
                            )
                            raise ValueError(
                                f"Task {task_id} snapshot integrity check failed and resume was rejected: {integrity_error}"
                            )
                    request_state = pending_action.get("requestState") if isinstance(pending_action.get("requestState"), dict) else {}
                    for key, value in request_state.items():
                        if key not in request or request.get(key) is None:
                            request[key] = value
            runtime_timings["loadTaskStateMs"] = _elapsed_ms(task_load_started_at)

            current_context = request.get("currentContext") if isinstance(request.get("currentContext"), list) else _load_snapshot_context(snapshot)
            protected_items = request.get("protectedItems") if isinstance(request.get("protectedItems"), list) else []
            task_type = _infer_task_type(task, request)
            run_type = str(request.get("runType") or "main")
            resume_path = (
                "restart-snapshot"
                if snapshot is not None and command == "resume" and snapshot.snapshot_type == "restart"
                else "snapshot"
                if snapshot is not None and command == "resume"
                else None
            )
            build_root_mount_started_at = perf_counter()
            root_mount = build_root_mount_package(
                task_id,
                {
                    "projectId": task.project_id,
                    "branchId": task.branch_id,
                    "spaceId": task.space_id,
                    "taskObjective": request.get("taskObjective") or task.current_objective or task.goal,
                    "currentObjective": request.get("currentObjective") or task.current_objective,
                    "currentFocus": request.get("currentFocus") or task.current_focus,
                    "resumeMessage": request.get("resumeMessage") or (snapshot.resume_message if snapshot else task.resume_message),
                    "restartMessage": request.get("restartMessage") or task.restart_message,
                    "responseRequirements": request.get("responseRequirements"),
                    "budgetState": request.get("budgetState") or task.budget.model_dump(by_alias=True),
                    "activeCapabilities": request.get("activeCapabilities") if isinstance(request.get("activeCapabilities"), list) else None,
                },
            )
            runtime_timings["buildRootMountMs"] = _elapsed_ms(build_root_mount_started_at)

            rehydration_result = None
            if snapshot is not None and command == "resume":
                rehydration_started_at = perf_counter()
                rehydration_results = collect_hook_results(
                    HookNames.TASK_RESUME_REHYDRATE,
                    {
                        "taskId": task.id,
                        "taskSnapshot": snapshot.model_dump(by_alias=True, mode="json"),
                        "rootMounts": root_mount,
                        "resumePolicy": {
                            "resumePath": "snapshot",
                            "preserveProtectedItems": True,
                        },
                    },
                    module_ids=root_mount.get("activeCapabilities") or None,
                )
                merged_restored_state: dict[str, Any] = {}
                followup_actions: list[dict[str, Any]] = []
                resume_summaries: list[str] = []
                for item in rehydration_results:
                    if item.get("error"):
                        raise RuntimeError(f"Resume rehydrate failed in {item.get('moduleId')}: {item['error']}")
                    result = item.get("result") if isinstance(item.get("result"), dict) else {}
                    restored_state = result.get("restoredState") if isinstance(result.get("restoredState"), dict) else {}
                    merged_restored_state.update(restored_state)
                    if isinstance(result.get("followupActions"), list):
                        followup_actions.extend(action for action in result["followupActions"] if isinstance(action, dict))
                    if result.get("resumeMessage") is not None:
                        request["resumeMessage"] = str(result["resumeMessage"])
                        root_mount["resumeMessage"] = str(result["resumeMessage"])
                    if result.get("summary") is not None:
                        resume_summaries.append(str(result["summary"]))
                if isinstance(merged_restored_state.get("currentContext"), list):
                    current_context = [item for item in merged_restored_state["currentContext"] if isinstance(item, dict)]
                if isinstance(merged_restored_state.get("protectedItems"), list):
                    protected_items = [item for item in merged_restored_state["protectedItems"] if isinstance(item, dict)]
                if isinstance(merged_restored_state.get("requestUpdates"), dict):
                    request.update(merged_restored_state["requestUpdates"])
                if isinstance(merged_restored_state.get("rootMount"), dict):
                    root_mount.update(merged_restored_state["rootMount"])
                if followup_actions:
                    request["pendingActions"] = [
                        action
                        for action in [*(request.get("pendingActions") or []), *followup_actions]
                        if isinstance(action, dict)
                    ]
                if resume_summaries:
                    root_mount["rootSummary"] = " ".join([root_mount.get("rootSummary") or "", *resume_summaries]).strip()
                rehydration_result = {
                    "restoredState": merged_restored_state,
                    "followupActions": followup_actions,
                    "summaries": resume_summaries,
                }
                runtime_timings["resumeRehydrateMs"] = _elapsed_ms(rehydration_started_at)

            seeded_takeover_protocol = False
            if _coerce_takeover_protocol(request.get("takeoverProtocol")) is None:
                seeded_protocol = build_task_takeover_protocol(
                    task=task,
                    task_type=task_type,
                    run_type=run_type,
                    request=request,
                    root_mount=root_mount,
                    current_context=current_context,
                )
                if seeded_protocol is not None:
                    seeded_takeover_protocol = True
                    request["takeoverProtocol"] = seeded_protocol.model_dump(by_alias=True, mode="json")
                    request["taskObjective"] = seeded_protocol.objective
                    request.setdefault("currentObjective", seeded_protocol.objective)
                    if request.get("currentFocus") is None and seeded_protocol.plan:
                        request["currentFocus"] = seeded_protocol.plan[0].title
                    root_mount["taskObjective"] = seeded_protocol.objective
                    root_mount["takeoverProtocol"] = request["takeoverProtocol"]

            pre_retrieval_context = [dict(item) for item in current_context if isinstance(item, dict)]
            memory_retrieval_started_at = perf_counter()
            execution_root_id = task.execution_root_node_id or root_mount["executionRefs"][0]["id"]
            memory_context = _retrieve_context_from_memory_tree(
                session,
                task=task,
                request=request,
                root_mount=root_mount,
                current_context=current_context,
                execution_root_id=str(execution_root_id),
            )
            retrieved_context_items = memory_context.get("contextItems") if isinstance(memory_context.get("contextItems"), list) else []
            if retrieved_context_items:
                current_context = [item for item in retrieved_context_items if isinstance(item, dict)]
                request["currentContext"] = [dict(item) for item in current_context]
            retrieved_protected_items = memory_context.get("protectedItems") if isinstance(memory_context.get("protectedItems"), list) else []
            if retrieved_protected_items:
                protected_items = [
                    item
                    for item in [*protected_items, *retrieved_protected_items]
                    if isinstance(item, dict)
                ]
            if memory_context.get("summary"):
                root_mount["rootSummary"] = " ".join(
                    item for item in [root_mount.get("rootSummary") or "", str(memory_context["summary"])] if item
                ).strip()
            retrieval_state = {
                "requestId": str((memory_context.get("retrievalRequest") or {}).get("id") or ""),
                "summary": str(memory_context.get("summary") or ""),
                "matchedNodeRefs": [
                    dict(item)
                    for item in (memory_context.get("protectedItems") or [])
                    if isinstance(item, dict)
                ],
                "materializedNodeIds": [str(node_id) for node_id in memory_context.get("materializedNodeIds") or []],
                "reverseTraceMode": bool((memory_context.get("retrievalRequest") or {}).get("reverseTraceMode", False)),
                "workTreeNodeId": (memory_context.get("retrievalRequest") or {}).get("workTreeNodeId"),
                "windowIndex": (memory_context.get("retrievalRequest") or {}).get("windowIndex"),
            }
            request["memoryRetrievalState"] = retrieval_state
            root_mount["memoryRetrievalState"] = dict(retrieval_state)
            runtime_timings["memoryRetrievalMs"] = _elapsed_ms(memory_retrieval_started_at)

            takeover_prepare_started_at = perf_counter()
            takeover_protocol = None if seeded_takeover_protocol else _coerce_takeover_protocol(request.get("takeoverProtocol"))
            if takeover_protocol is None:
                takeover_protocol = build_task_takeover_protocol(
                    task=task,
                    task_type=task_type,
                    run_type=run_type,
                    request=request,
                    root_mount=root_mount,
                    current_context=current_context,
                )
            if takeover_protocol is not None:
                request["takeoverProtocol"] = takeover_protocol.model_dump(by_alias=True, mode="json")
                request["taskObjective"] = takeover_protocol.objective
                request.setdefault("currentObjective", takeover_protocol.objective)
                if request.get("currentFocus") is None and takeover_protocol.plan:
                    request["currentFocus"] = takeover_protocol.plan[0].title
                root_mount["taskObjective"] = takeover_protocol.objective
                root_mount["rootSummary"] = " ".join(
                    item for item in [root_mount.get("rootSummary") or "", takeover_protocol.objective_summary] if item
                ).strip()
            runtime_timings["takeoverPrepareMs"] = _elapsed_ms(takeover_prepare_started_at)

            context_length_observations: list[dict[str, Any]] = []
            if current_context:
                if resume_path == "restart-snapshot":
                    _append_context_length_observation(
                        context_length_observations,
                        phase="afterWindowRestart",
                        source="carryForwardContext",
                        items=current_context,
                        trigger="restartSnapshot",
                    )
                _append_context_length_observation(
                    context_length_observations,
                    phase="beforeContextPruning",
                    source="currentContext",
                    items=current_context,
                )
                restart_message = request.get("restartMessage") or task.restart_message
                if restart_message:
                    _append_context_length_observation(
                        context_length_observations,
                        phase="beforeWindowRestart",
                        source="currentContext",
                        items=current_context,
                        trigger="restartMessage",
                    )

            prepare_run_started_at = perf_counter()
            runtime_metrics = _runtime_metrics(task, request)
            input_tokens, output_tokens = _estimate_usage(task, root_mount, current_context, request)
            budget_limit = _remaining_cost_per_1k(task.budget, input_tokens + output_tokens)
            min_quality = float(request.get("minQuality", 0.0)) if request.get("minQuality") is not None else None
            runtime_candidates = load_runtime_candidate_models()
            required_context_window = (
                int(request["requiredContextWindow"])
                if request.get("requiredContextWindow") is not None
                else runtime_metrics["effectiveContextWindow"]
                if runtime_metrics["effectiveContextWindow"] > 0
                else None
            )
            route_preview = build_model_route_decision(
                task_type,
                task_id=task_id,
                candidates=request.get("candidateModels") if isinstance(request.get("candidateModels"), list) else runtime_candidates,
                budget_limit=budget_limit,
                required_context_window=required_context_window,
                min_quality=min_quality,
            )
            estimated_cost = round(
                (input_tokens + output_tokens) * float(route_preview["candidateModels"][0]["costPer1k"]) / 1000.0,
                6,
            )
            _enforce_budget(task.budget, input_tokens=input_tokens, output_tokens=output_tokens, estimated_cost=estimated_cost)

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
                    "windowIndex": runtime_metrics["windowIndex"],
                    "restartCount": runtime_metrics["restartCount"],
                    "cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
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
                    "windowIndex": runtime_metrics["windowIndex"],
                    "restartCount": runtime_metrics["restartCount"],
                    "cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
                    "carryForwardLossCount": runtime_metrics["carryForwardLossCount"],
                },
            )
            runtime_timings["prepareRunMs"] = _elapsed_ms(prepare_run_started_at)
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
                task = task_repository.update_task(task_id, {"activeSnapshotId": None, "restartMessage": None})
                resumed_locator = (
                    f"agent-runtime/tasks/{task.id}/restart/{run.id}"
                    if resume_path == "restart-snapshot"
                    else f"agent-runtime/tasks/{task.id}/resume/{run.id}"
                )
                _cache_package_entry(
                    coordinator,
                    resumed_locator,
                    {
                        "snapshotId": snapshot.id,
                        "restoredFromCheckpoint": True,
                        "resumePath": resume_path,
                    },
                )
                resume_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task",
                    aggregate_id=task.id,
                    event_type="task.resumed",
                    locator=resumed_locator,
                )
                restart_completed_event = None
                if resume_path == "restart-snapshot":
                    restart_completed_event = _persist_runtime_event(
                        session,
                        project_id=task.project_id,
                        aggregate_type="task",
                        aggregate_id=task.id,
                        event_type="context.restart.completed",
                        locator=resumed_locator,
                    )
                resume_event_payload = {
                    "snapshot": resumed_snapshot.model_dump(by_alias=True, mode="json"),
                    "outboxRecord": resume_event.model_dump(by_alias=True, mode="json"),
                    "resumePath": resume_path,
                }
                if restart_completed_event is not None:
                    resume_event_payload["contextRestartCompleted"] = restart_completed_event.model_dump(by_alias=True, mode="json")

            pruning_result = None
            pruning_events = None
            if current_context:
                pruning_started_at = perf_counter()
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
                        retained_items = pruning_result.get("retainedItems") if isinstance(pruning_result.get("retainedItems"), list) else []
                        if retained_items:
                            _append_context_length_observation(
                                context_length_observations,
                                phase="afterContextPruning",
                                source="currentContext",
                                items=retained_items,
                            )
                runtime_timings["contextPruningMs"] = _elapsed_ms(pruning_started_at)

            execution_actor_id = str(request.get("executionActorId") or ("subagent" if run_type == "subagent" else "main-agent"))
            llm_invoke_started_at = perf_counter()
            effective_context = pruning_result.get("retainedItems") if isinstance(pruning_result, dict) and isinstance(pruning_result.get("retainedItems"), list) else current_context
            if pruning_result is not None:
                runtime_metrics["compressionCount"] = int(runtime_metrics["compressionCount"]) + 1
            restart_trigger, window_span_tokens = _window_restart_trigger(request, runtime_metrics, effective_context)
            runtime_metrics["windowSpanTokens"] = window_span_tokens
            request["runtimeMetrics"] = dict(runtime_metrics)
            if context_length_observations:
                request["contextLengthObservations"] = [dict(item) for item in context_length_observations]
            if restart_trigger is not None:
                return _handle_window_restart_transition(
                    session=session,
                    coordinator=coordinator,
                    task_repository=task_repository,
                    task=task,
                    run=run,
                    route_decision=route_decision,
                    task_id=task_id,
                    request=request,
                    root_mount=root_mount,
                    runtime_metrics=runtime_metrics,
                    context_length_observations=context_length_observations,
                    effective_context=effective_context,
                    pre_retrieval_context=pre_retrieval_context,
                    protected_items=protected_items,
                    pruning_result=pruning_result,
                    pruning_events=pruning_events,
                    run_created_event=run_created_event,
                    route_event=route_event,
                    resume_event_payload=resume_event_payload,
                    rehydration_result=rehydration_result,
                    runtime_timings=runtime_timings,
                    work_started_at=work_started_at,
                    restart_trigger=restart_trigger,
                    window_span_tokens=window_span_tokens,
                )
            registered_tools_override = [
                dict(item)
                for item in request.get("registeredTools") or []
                if isinstance(item, dict)
            ] if isinstance(request.get("registeredTools"), list) else None
            try:
                llm_result = invoke_runtime_completion(
                    session,
                    task=task,
                    run=run,
                    route_decision=route_decision,
                    task_type=task_type,
                    root_mount=root_mount,
                    current_context=effective_context,
                    request=request,
                    resume_path=resume_path,
                    registered_tools=registered_tools_override,
                )
            except SafeShutdownInterrupt as _shutdown_exc:
                _logger.info(
                    "Safe shutdown requested during tool execution for task %s (invocation %s, round %d, %d pending tool calls). Saving checkpoint.",
                    task_id,
                    _shutdown_exc.invocation_id,
                    _shutdown_exc.round_index,
                    len(_shutdown_exc.pending_tool_calls),
                )
                snap_result = save_pending_tool_calls_snapshot(
                    task_id,
                    agent_run_id=run.id,
                    pending_tool_calls=_shutdown_exc.pending_tool_calls,
                    conversation_messages=_shutdown_exc.conversation_messages,
                    assistant_message=_shutdown_exc.assistant_message,
                    invocation_id=_shutdown_exc.invocation_id,
                    round_index=_shutdown_exc.round_index,
                    usage_totals=_shutdown_exc.usage_totals,
                    accumulated_cost=_shutdown_exc.accumulated_cost,
                    round_summaries=_shutdown_exc.round_summaries,
                    round_modes=_shutdown_exc.round_modes,
                    current_context_state=effective_context,
                    root_mount_preview=root_mount,
                    app_id=task.app_id,
                    project_id=task.project_id,
                    branch_id=task.branch_id,
                    lock_already_held=True,
                    session_override=session,
                    request_state=_build_restart_request_state(
                        request,
                        request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {},
                    ),
                )
                task_repository.update_agent_run(run.id, {"status": "paused"})
                return {
                    "status": "shutdown-checkpoint",
                    "taskId": task_id,
                    "snapshotId": snap_result.get("id"),
                    "resumeToken": snap_result.get("resumeToken"),
                    "persisted": snap_result.get("persisted"),
                    "pendingToolCallCount": len(_shutdown_exc.pending_tool_calls),
                }
            runtime_timings["llmInvocationMs"] = _elapsed_ms(llm_invoke_started_at)
            actual_input_tokens = int(llm_result["usage"].get("inputTokens", input_tokens))
            actual_output_tokens = int(llm_result["usage"].get("outputTokens", output_tokens))
            actual_cost = float(llm_result.get("costUsed", estimated_cost))
            runtime_metrics_artifact: dict[str, Any] | None = None
            invocation_id = str((llm_result.get("invocation") or {}).get("id") or "").strip()
            if invocation_id:
                metrics_snapshot = _build_runtime_metrics_snapshot(
                    runtime_metrics=runtime_metrics,
                    llm_result=llm_result,
                )
                runtime_metrics_artifact = _persist_runtime_metrics_artifact(
                    session,
                    task=task,
                    invocation_id=invocation_id,
                    metrics_snapshot=metrics_snapshot,
                )
            budget_overrun: str | None = None
            llm_budget_check = llm_result.get("budgetCheckResult") if isinstance(llm_result.get("budgetCheckResult"), dict) else None
            llm_budget_overrun = llm_result.get("budgetOverrunResult") if isinstance(llm_result.get("budgetOverrunResult"), dict) else None
            if llm_budget_check is not None and not bool(llm_budget_check.get("checkPassed", True)):
                budget_overrun = str(llm_budget_check.get("reason") or "Pre-invocation budget check failed.")
            elif llm_budget_overrun is not None and bool(llm_budget_overrun.get("isOverrun", False)):
                violation_type = str(llm_budget_overrun.get("violationType") or "budget")
                budget_overrun = f"{violation_type.capitalize()} budget exceeded after model invocation."
            if budget_overrun is None:
                try:
                    _enforce_consumed_budget(
                        task.budget,
                        input_tokens=actual_input_tokens,
                        output_tokens=actual_output_tokens,
                        cost_used=actual_cost,
                    )
                except ValueError as exc:
                    budget_overrun = str(exc)
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
                    "status": "failed" if budget_overrun is not None else task.status,
                    "currentFocus": f"execution-failed: {budget_overrun}" if budget_overrun is not None else task.current_focus,
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
            if budget_overrun is not None:
                run = task_repository.update_agent_run(run.id, {"status": "failed"})
                window_execution_artifact = _persist_window_execution_artifact(
                    session,
                    task=task,
                    run=run,
                    record=_build_window_execution_record(
                        task=task,
                        run=run,
                        request=request,
                        root_mount=root_mount,
                        runtime_metrics=runtime_metrics,
                        current_context=effective_context,
                        pre_retrieval_context=pre_retrieval_context,
                        protected_items=protected_items,
                        llm_result=llm_result,
                        transition_stage="window-delivery",
                        transition_outcome="failed",
                        resume_path=resume_path,
                        source_snapshot_id=snapshot.id if snapshot is not None and command == "resume" else None,
                        rehydration_result=rehydration_result,
                    ),
                )
                runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
                return {
                    "status": "failed",
                    "taskId": task_id,
                    "task": task.model_dump(by_alias=True, mode="json"),
                    "run": run.model_dump(by_alias=True, mode="json"),
                    "routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
                    "modelInvocation": llm_result["invocation"],
                    "outboxRecords": {
                        "modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
                        "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                        "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                    },
                    "windowExecutionArtifact": window_execution_artifact,
                    "runtimeMetricsArtifact": runtime_metrics_artifact,
                    "detail": budget_overrun,
                    "runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
                }
            memory_tag_write_result = _apply_assistant_memory_write_tags(
                session,
                task=task,
                run=run,
                request=request,
                root_mount=root_mount,
                execution_root_id=str(execution_root_id),
                llm_result=llm_result,
                execution_actor_id=execution_actor_id,
            )
            request["memoryTagWrites"] = memory_tag_write_result
            invocation_id = str((llm_result.get("invocation") or {}).get("id") or "").strip()
            if invocation_id:
                try:
                    runtime_repository.update_model_invocation(
                        invocation_id,
                        {
                            "outputLabels": _model_invocation_output_labels(request, memory_tag_write_result),
                            "assistantTextSummary": _assistant_text_summary(str(llm_result.get("assistantText") or "")),
                        },
                    )
                except KeyError:
                    pass
            takeover_finalize_started_at = perf_counter()
            takeover_protocol = finalize_task_takeover_protocol(
                takeover_protocol,
                task=task,
                request=request,
                root_mount=root_mount,
                current_context=effective_context,
                llm_result=llm_result,
            )
            takeover_protocol_ref = (
                persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=run.id)
                if takeover_protocol is not None
                else None
            )
            if takeover_protocol is not None:
                request["takeoverProtocol"] = takeover_protocol.model_dump(by_alias=True, mode="json")
                root_mount["takeoverProtocol"] = request["takeoverProtocol"]
            runtime_timings["takeoverFinalizeMs"] = _elapsed_ms(takeover_finalize_started_at)
            memory_write_started_at = perf_counter()
            write_payload = _build_execution_write_payload(
                task=task,
                task_type=task_type,
                root_mount=root_mount,
                route_decision=route_decision.model_dump(by_alias=True, mode="json"),
                model_output=str(llm_result["assistantText"]),
                model_invocation=llm_result["invocation"],
                tool_executions=llm_result.get("toolExecutions"),
                pruning_result=pruning_result,
                resume_path=resume_path,
                takeover_protocol=takeover_protocol,
                takeover_protocol_ref=takeover_protocol_ref,
            )
            write_validation = validate_memory_write(
                {
                    "taskId": task.id,
                    "projectId": task.project_id,
                    "hostSpaceId": task.space_id,
                    "ownerProfileId": task.owner_profile_id,
                    "subject": request.get("subject") or f"profile:{task.owner_profile_id}",
                    "relation": "write",
                    "nodePayload": write_payload,
                    "candidateNodes": [
                        {
                            "id": new_id("candnode", task.id, run.id, stable=True),
                            "title": write_payload["title"],
                            "content": write_payload["content"],
                            "parentId": execution_root_id,
                            "rootBranch": "execution",
                            "nodeType": "task",
                        }
                    ],
                    "candidateEdges": [],
                    "ownerProfileId": task.owner_profile_id,
                    "subject": request.get("subject") or f"profile:{task.owner_profile_id}",
                    "relation": "write",
                    "nodePayload": write_payload,
                    "rootMount": root_mount,
                    "resumePath": resume_path,
                },
                module_ids=root_mount.get("activeCapabilities") or None,
            )
            if not write_validation["allowed"]:
                raise PermissionError("Memory write validation failed: " + "; ".join(write_validation["blockers"]))
            if takeover_protocol is not None and takeover_protocol_ref is not None:
                write_validation.setdefault("annotations", []).append(
                    {
                        "id": new_id("srcann", task.id, run.id, "takeover", stable=True),
                        "sourceType": "system",
                        "sourceRef": takeover_protocol_ref.model_dump(mode="json"),
                        "excerpt": summarize_task_takeover_protocol(takeover_protocol),
                        "inferenceSummary": "Formal task takeover protocol for this run.",
                        "confidence": 1.0,
                        "createdBy": {"type": "module", "id": "task-takeover"},
                    }
                )
            target_space_id = str(write_validation.get("targetSpaceId") or task.space_id)
            target_branch_id = str(write_validation.get("targetBranchId") or task.branch_id)
            if target_space_id != task.space_id or target_branch_id != task.branch_id:
                WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                    branch_id=target_branch_id,
                    project_id=task.project_id,
                    space_id=target_space_id,
                )
            created_node = node_repository.create_node(
                {
                    "projectId": task.project_id,
                    "spaceId": target_space_id,
                    "branchId": target_branch_id,
                    "parentId": execution_root_id,
                    "rootBranch": "execution",
                    "nodeType": "task",
                    "title": write_payload["title"],
                    "content": write_payload["content"],
                    "windowIndex": max(_int_metric(runtime_metrics.get("windowIndex"), 1), 1),
                    "sourceWorkTreeNodeId": _work_tree_node_id_from_request(request),
                    "createdBy": {"type": "agent", "id": execution_actor_id},
                    "updatedBy": {"type": "agent", "id": execution_actor_id},
                    "changeReason": f"{run_type}-agent-execution",
                }
            )
            for index, annotation in enumerate(
                [annotation for annotation in write_validation.get("annotations") or [] if isinstance(annotation, dict)],
                start=1,
            ):
                node_repository.add_source_annotation(
                    "node",
                    created_node.id,
                    {
                        "id": annotation.get("id") or new_id("srcann", created_node.id, index, stable=True),
                        "projectId": task.project_id,
                        "branchId": target_branch_id,
                        "sourceType": annotation.get("sourceType") or "memory",
                        "sourceRef": annotation.get("sourceRef"),
                        "excerpt": annotation.get("excerpt"),
                        "inferenceSummary": annotation.get("inferenceSummary") or annotation.get("summary"),
                        "evidenceRefs": annotation.get("evidenceRefs") or [],
                        "confidence": float(annotation.get("confidence", 0.85)),
                        "createdBy": annotation.get("createdBy") or {"type": "module", "id": "runtime-kernel"},
                    },
                )
            write_event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="node",
                aggregate_id=created_node.id,
                event_type="node.created",
                locator=f"agent-runtime/tasks/{task.id}/writes/{created_node.id}",
            )
            runtime_timings["memoryWriteMs"] = _elapsed_ms(memory_write_started_at)

            session.expire_all()
            fresh_task = task_repository.get_task(task_id)
            if fresh_task is not None:
                task = fresh_task

            return _finalize_execution_transition(
                session=session,
                coordinator=coordinator,
                task_repository=task_repository,
                task_id=task_id,
                task=task,
                run=run,
                route_decision=route_decision,
                request=request,
                root_mount=root_mount,
                created_node=created_node,
                llm_result=llm_result,
                pruning_result=pruning_result,
                pruning_events=pruning_events,
                takeover_protocol=takeover_protocol,
                takeover_protocol_ref=takeover_protocol_ref,
                model_invocation_event=model_invocation_event,
                run_created_event=run_created_event,
                route_event=route_event,
                write_event=write_event,
                resume_event_payload=resume_event_payload,
                memory_tag_write_result=memory_tag_write_result,
                write_validation=write_validation,
                rehydration_result=rehydration_result,
                runtime_metrics_artifact=runtime_metrics_artifact,
                runtime_timings=runtime_timings,
                work_started_at=work_started_at,
                current_context=effective_context,
            )
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
        except Exception as exc:  # noqa: BLE001
            _logger.warning("Failed to persist failed status for task (task_id=%s): %s", task_id, exc)
        return {
            "status": "failed",
            "taskId": task_id,
            "detail": str(exc),
            "runtimeTimings": {**runtime_timings, "totalMs": _elapsed_ms(work_started_at)},
        }
    finally:
        coordinator.release_lock(f"task:{task_id}", lock_owner)
__all__ = [name for name in globals() if not name.startswith("__")]
