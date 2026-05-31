from .execution_loop_state import *  # noqa: F401,F403
from .execution_loop_transitions import _finalize_execution_transition
from .root_mount import _elapsed_ms, _infer_task_type, build_task_runtime_state
def _mailbox_context_item(message: dict[str, Any]) -> dict[str, Any]:
    subject = normalize_excerpt(str(message.get("subject") or message.get("messageKind") or "Mailbox message"), 160)
    body = normalize_excerpt(str(message.get("body") or message.get("summary") or subject or ""), 320)
    return {
        "kind": "mailbox-message",
        "id": str(message.get("id") or "mailbox-message"),
        "mailboxMessageId": str(message.get("id") or "mailbox-message"),
        "title": subject or "Mailbox message",
        "content": body or subject or "Mailbox message",
        "messageKind": str(message.get("messageKind") or "message"),
        "workTreeNodeId": str(message.get("workTreeNodeId") or "").strip() or None,
        "createdAt": message.get("createdAt"),
        "importance": 1.0,
    }
def _hydrate_mailbox_runtime_state(
    *,
    task,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    runtime_repository: RuntimeRepository,
) -> list[dict[str, Any]]:
    mailbox_messages = root_mount.get("mailboxMessages") if isinstance(root_mount.get("mailboxMessages"), list) else []
    if not mailbox_messages:
        return current_context

    existing_ids = {
        str(item.get("mailboxMessageId") or "")
        for item in current_context
        if isinstance(item, dict) and str(item.get("kind") or "") == "mailbox-message"
    }
    delivered_ids: list[str] = []
    new_context_items: list[dict[str, Any]] = []
    latest_subject: str | None = None
    latest_node_id: str | None = None
    for message in mailbox_messages:
        if not isinstance(message, dict):
            continue
        message_id = str(message.get("id") or "").strip()
        if not message_id:
            continue
        delivered_ids.append(message_id)
        latest_subject = str(message.get("subject") or "").strip() or latest_subject
        node_id = str(message.get("workTreeNodeId") or "").strip() or None
        latest_node_id = node_id or latest_node_id
        if message_id not in existing_ids:
            new_context_items.append(_mailbox_context_item(message))

    if new_context_items:
        current_context = [*new_context_items, *current_context]
        request["currentContext"] = [dict(item) for item in current_context]

    if latest_subject and not str(request.get("currentObjective") or "").strip():
        request["currentObjective"] = normalize_excerpt(latest_subject, 160)
    if latest_subject and not str(request.get("currentFocus") or "").strip():
        request["currentFocus"] = normalize_excerpt(f"mailbox: {latest_subject}", 96)
    if latest_node_id is not None and not str(request.get("currentNodeId") or "").strip():
        request["currentNodeId"] = latest_node_id
        request.setdefault("workTreeNodeId", latest_node_id)
        request.setdefault("workingNodeAnnotation", f"<Working_Node: {latest_node_id}>")
        memory_retrieval_state = dict(request.get("memoryRetrievalState") or {})
        memory_retrieval_state["workTreeNodeId"] = latest_node_id
        request["memoryRetrievalState"] = memory_retrieval_state

    if delivered_ids:
        runtime_repository.update_mailbox_message_status(task_id=task.id, message_ids=delivered_ids, status="delivered")
        root_mount["mailboxState"] = runtime_repository.get_mailbox_state(task.id)
        root_mount["mailboxMessages"] = []
        root_summary = str(root_mount.get("rootSummary") or "").strip()
        mailbox_summary = f"Mailbox delivered messages: {len(delivered_ids)}."
        root_mount["rootSummary"] = " ".join(part for part in (root_summary, mailbox_summary) if part).strip()
        standby_state = root_mount.get("standbyState") if isinstance(root_mount.get("standbyState"), dict) else {}
        root_mount["standbyState"] = {
            **standby_state,
            "pendingMailboxCount": int(root_mount["mailboxState"].get("pendingCount") or 0),
        }
    return current_context
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

    retrieval_focus = (
        _work_tree_focus_label(_coerce_takeover_protocol(request.get("takeoverProtocol")))
        or str(request.get("currentFocus") or task.current_focus or "")
    )
    retrieval_query = " ".join(
        part.strip()
        for part in [
            str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal or ""),
            retrieval_focus,
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
    if _should_trim_retrieved_context(current_context, request=request):
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
def _mark_takeover_execution_failed(
    *,
    request: dict[str, Any],
    root_mount: dict[str, Any] | None,
    takeover_protocol: TaskTakeoverProtocol | None,
    task_id: str,
    agent_run_id: str,
    failure_summary: str,
) -> tuple[TaskTakeoverProtocol | None, dict[str, Any] | None, dict[str, Any] | None]:
    if takeover_protocol is None or takeover_protocol.work_tree is None:
        return takeover_protocol, request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None, None
    try:
        failed_protocol, failed_stack, failure_transition = fail_current_work_node(
            takeover_protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            failure_summary=failure_summary,
            work_context_stack=request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None,
        )
        failed_protocol, failed_stack = sync_takeover_runtime_state(
            request,
            root_mount,
            failed_protocol,
            task_id=task_id,
            agent_run_id=agent_run_id,
            current_focus=(failure_transition or {}).get("currentFocus") if isinstance(failure_transition, dict) else None,
            work_context_stack=failed_stack,
        )
        stack_payload = failed_stack.model_dump(by_alias=True, mode="json") if failed_stack is not None else None
        if stack_payload is not None:
            request["workContextStack"] = stack_payload
            if isinstance(root_mount, dict):
                root_mount["workContextStack"] = stack_payload
        return failed_protocol, stack_payload, failure_transition
    except Exception:  # noqa: BLE001
        return takeover_protocol, request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None, None
def _queue_takeover_failure_continuation(
    *,
    session,
    coordinator: RedisCoordinator,
    task_repository: TaskRepository,
    task,
    run,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    takeover_protocol: TaskTakeoverProtocol | None,
    failure_transition: dict[str, Any] | None,
    detail: str,
    runtime_metrics: dict[str, Any],
    current_context: list[dict[str, Any]],
    pre_retrieval_context: list[dict[str, Any]] | None,
    protected_items: list[dict[str, Any]] | None,
    transition_stage: str,
    continuation_suffix: str,
    resume_event_payload: dict[str, Any] | None,
    rehydration_result: dict[str, Any] | None,
):
    stack_payload = request.get("workContextStack") if isinstance(request.get("workContextStack"), dict) else None
    if not (
        isinstance(failure_transition, dict)
        and bool(failure_transition.get("requiresContinuation"))
        and takeover_protocol is not None
        and takeover_protocol.work_tree is not None
        and isinstance(stack_payload, dict)
    ):
        return None
    takeover_protocol_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=run.id)
    stack_model = WorkContextStack.model_validate(stack_payload)
    work_context_stack_ref = persist_stack_snapshot(stack_model, task_id=task.id, run_id=run.id).model_dump(mode="json")
    continuation_payload = build_takeover_continuation_request(
        request,
        protocol=takeover_protocol,
        work_context_stack=stack_model,
        parent_run_id=run.id,
        current_focus=(failure_transition or {}).get("currentFocus") if isinstance(failure_transition, dict) else None,
    )
    continuation_payload["workContextStackRef"] = work_context_stack_ref
    queued_work_item = {
        "activity": "core.agent.main.execute",
        "taskId": task.id,
        "command": "start",
        "requestedAt": utc_now().isoformat(),
        "payload": continuation_payload,
    }
    queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, queued_work_item)
    continuation_locator = f"agent-runtime/tasks/{task.id}/continuations/{run.id}/{continuation_suffix}"
    _cache_package_entry(
        coordinator,
        continuation_locator,
        {
            "sourceRunId": run.id,
            "currentNodeId": continuation_payload.get("currentNodeId"),
            "topFrameId": continuation_payload.get("topFrameId"),
            "stackDigest": continuation_payload.get("stackDigest"),
            "workContextStackRef": work_context_stack_ref,
            "transition": (failure_transition or {}).get("transition"),
            "queueDepth": queue_depth,
        },
    )
    continuation_event = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="task",
        aggregate_id=task.id,
        event_type="task.continuation.queued",
        locator=continuation_locator,
    )
    run = task_repository.update_agent_run(
        run.id,
        {
            "status": "completed",
            "windowIndex": runtime_metrics.get("windowIndex") or task.window_index or 1,
            "restartCount": runtime_metrics.get("restartCount") or task.restart_count or 0,
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens") or task.cumulative_window_span_tokens or 0,
        },
    )
    task = task_repository.update_task(
        task.id,
        {
            "status": "queued",
            "currentFocus": (failure_transition or {}).get("currentFocus") or detail,
            "windowIndex": runtime_metrics.get("windowIndex") or task.window_index or 1,
            "restartCount": runtime_metrics.get("restartCount") or task.restart_count or 0,
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens") or task.cumulative_window_span_tokens or 0,
            "carryForwardLossCount": runtime_metrics.get("carryForwardLossCount") or task.carry_forward_loss_count or 0,
        },
    )
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
            current_context=current_context,
            pre_retrieval_context=pre_retrieval_context,
            protected_items=protected_items,
            transition_stage=transition_stage,
            transition_outcome=str((failure_transition or {}).get("transition") or "bubble-parent-after-failure"),
            resume_path=(resume_event_payload or {}).get("resumePath") if isinstance(resume_event_payload, dict) else None,
            source_snapshot_id=(resume_event_payload or {}).get("snapshot", {}).get("id") if isinstance((resume_event_payload or {}).get("snapshot"), dict) else None,
            rehydration_result=rehydration_result,
        ),
    )
    return {
        "task": task,
        "run": run,
        "takeoverProtocolRef": takeover_protocol_ref,
        "queuedWorkItem": queued_work_item,
        "queueDepth": queue_depth,
        "workContextStackRef": work_context_stack_ref,
        "windowExecutionArtifact": window_execution_artifact,
        "continuationEvent": continuation_event,
    }
