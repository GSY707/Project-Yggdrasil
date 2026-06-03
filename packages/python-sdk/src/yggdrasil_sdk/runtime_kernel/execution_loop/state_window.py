from .state_metrics import *  # noqa: F403,F401

def _stable_digest(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        normalized_text = " ".join(value.split()).strip()
        if not normalized_text:
            return None
        payload = normalized_text
    else:
        payload = value
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if serialized in {'""', "[]", "{}"}:
        return None
    return sha1(serialized.encode("utf-8")).hexdigest()[:16]
def _normalize_entity_ids(items: list[Any] | None) -> list[str]:
    normalized_ids: list[str] = []
    for item in items or []:
        candidate = item
        if isinstance(item, dict):
            candidate = item.get("id")
            if candidate is None and isinstance(item.get("ref"), dict):
                candidate = item["ref"].get("id")
        normalized = str(candidate or "").strip()
        if normalized and normalized not in normalized_ids:
            normalized_ids.append(normalized)
    return normalized_ids
def _looks_like_planning_stub(text: str) -> bool:
    normalized = " ".join(str(text).split()).strip().lower()
    if not normalized:
        return False
    planning_markers = [
        "先总结当前局势",
        "当前局势",
        "最稳妥的下一步",
        "下一步",
        "建议按以下步骤",
    ]
    marker_hits = sum(1 for marker in planning_markers if marker in normalized)
    delivery_markers = [
        "任务价值判断",
        "联调覆盖范围",
        "关键集成链路",
        "acceptance 对照结论",
        "风险与下一步",
        "## 1.",
    ]
    has_delivery_structure = any(marker in normalized for marker in delivery_markers)
    return marker_hits >= 2 and not has_delivery_structure
def _window_execution_titles_preview(current_context: list[dict[str, Any]], limit: int = 5) -> list[str]:
    titles: list[str] = []
    for item in current_context:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("kind") or item.get("id") or "").strip()
        if title and title not in titles:
            titles.append(title)
        if len(titles) >= limit:
            break
    return titles
def _window_execution_memory_state(request: dict[str, Any]) -> dict[str, Any]:
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else {}
    matched_node_ids = _normalize_entity_ids(memory_retrieval_state.get("matchedNodeRefs") if isinstance(memory_retrieval_state.get("matchedNodeRefs"), list) else [])
    materialized_node_ids = _normalize_entity_ids(memory_retrieval_state.get("materializedNodeIds") if isinstance(memory_retrieval_state.get("materializedNodeIds"), list) else [])
    retrieval_fingerprint = _stable_digest(
        {
            "requestId": memory_retrieval_state.get("requestId"),
            "summary": memory_retrieval_state.get("summary"),
            "matchedNodeIds": matched_node_ids,
            "materializedNodeIds": materialized_node_ids,
            "reverseTraceMode": bool(memory_retrieval_state.get("reverseTraceMode", False)),
            "workTreeNodeId": memory_retrieval_state.get("workTreeNodeId"),
            "windowIndex": memory_retrieval_state.get("windowIndex"),
        }
    )
    return {
        "requestId": str(memory_retrieval_state.get("requestId") or "").strip() or None,
        "summary": str(memory_retrieval_state.get("summary") or "").strip() or None,
        "matchedNodeIds": matched_node_ids,
        "matchedNodeCount": len(matched_node_ids),
        "materializedNodeIds": materialized_node_ids,
        "materializedNodeCount": len(materialized_node_ids),
        "reverseTraceMode": bool(memory_retrieval_state.get("reverseTraceMode", False)),
        "workTreeNodeId": str(memory_retrieval_state.get("workTreeNodeId") or "").strip() or None,
        "windowIndex": _int_metric(memory_retrieval_state.get("windowIndex"), 0) or None,
        "retrievalFingerprint": retrieval_fingerprint,
    }
def _window_execution_cache_summary(llm_result: dict[str, Any] | None) -> dict[str, Any]:
    usage = (llm_result or {}).get("usage") if isinstance((llm_result or {}).get("usage"), dict) else {}
    input_tokens = max(_int_metric(usage.get("inputTokens"), 0), 0)
    cache_hit_input_tokens = max(_int_metric(usage.get("cacheHitInputTokens"), 0), 0)
    cache_write_input_tokens = max(_int_metric(usage.get("cacheWriteInputTokens"), 0), 0)
    non_cache_input_tokens = max(_int_metric(usage.get("nonCacheInputTokens"), max(input_tokens - cache_hit_input_tokens, 0)), 0)
    tracked_input_tokens = max(input_tokens, cache_hit_input_tokens + cache_write_input_tokens + non_cache_input_tokens, 0)
    denominator = tracked_input_tokens if tracked_input_tokens > 0 else 1
    return {
        "inputTokens": input_tokens,
        "cacheHitInputTokens": cache_hit_input_tokens,
        "cacheWriteInputTokens": cache_write_input_tokens,
        "nonCacheInputTokens": non_cache_input_tokens,
        "trackedInputTokens": tracked_input_tokens,
        "cacheHitRatio0_1": round(cache_hit_input_tokens / denominator, 4) if tracked_input_tokens > 0 else 0.0,
        "cacheWriteRatio0_1": round(cache_write_input_tokens / denominator, 4) if tracked_input_tokens > 0 else 0.0,
    }
def _coerce_work_context_stack_payload(candidate: Any) -> dict[str, Any] | None:
    if isinstance(candidate, WorkContextStack):
        return candidate.model_dump(by_alias=True, mode="json")
    if not isinstance(candidate, dict):
        return None
    try:
        return WorkContextStack.model_validate(candidate).model_dump(by_alias=True, mode="json")
    except Exception:
        return candidate
def _window_execution_work_tree_debug(
    work_context_stack: dict[str, Any] | None,
    *,
    current_node_id: str | None,
    transition_outcome: str,
    resume_path: str | None,
    restart_trigger: str | None,
) -> dict[str, Any]:
    stack_payload = _coerce_work_context_stack_payload(work_context_stack)
    frame_path: list[dict[str, Any]] = []
    child_status_counts: dict[str, int] = {}
    recent_child_completion_summaries: list[dict[str, Any]] = []
    active_path_node_ids: list[str] = []
    active_path_frame_ids: list[str] = []
    top_frame_id: str | None = None
    top_frame_node_id: str | None = current_node_id
    top_frame_prefix_cache_key: str | None = None
    continuation_reason: str | None = None
    if isinstance(stack_payload, dict):
        frames = stack_payload.get("frames") if isinstance(stack_payload.get("frames"), list) else []
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            frame_id = str(frame.get("id") or "").strip() or None
            node_id = str(frame.get("nodeId") or "").strip() or None
            prefix_cache_key = str(frame.get("prefixCacheKey") or "").strip() or None
            cursor_state = str(frame.get("cursorState") or "").strip() or None
            child_summaries = [
                item
                for item in frame.get("childCompletionSummaries") or []
                if isinstance(item, dict)
            ]
            frame_path.append(
                {
                    "frameId": frame_id,
                    "nodeId": node_id,
                    "parentFrameId": str(frame.get("parentFrameId") or "").strip() or None,
                    "stackDepth": max(_int_metric(frame.get("stackDepth"), 0), 0),
                    "status": str(frame.get("status") or "active").strip() or "active",
                    "cursorState": cursor_state,
                    "frameHeader": str(frame.get("frameHeader") or "").strip() or None,
                    "prefixCacheKey": prefix_cache_key,
                    "childCompletionCount": len(child_summaries),
                    "childCompletionStatuses": [str(item.get("status") or "completed") for item in child_summaries],
                }
            )
            if frame_id is not None:
                active_path_frame_ids.append(frame_id)
            if node_id is not None:
                active_path_node_ids.append(node_id)
            for summary in child_summaries:
                status = str(summary.get("status") or "completed").strip() or "completed"
                child_status_counts[status] = child_status_counts.get(status, 0) + 1
                recent_child_completion_summaries.append(
                    {
                        "frameId": frame_id,
                        "nodeId": node_id,
                        "childNodeId": str(summary.get("childNodeId") or "").strip() or None,
                        "status": status,
                        "summary": normalize_excerpt(str(summary.get("summary") or ""), 160) or None,
                    }
                )
            if frame_id == stack_payload.get("topFrameId"):
                top_frame_id = frame_id
                top_frame_node_id = node_id or top_frame_node_id
                top_frame_prefix_cache_key = prefix_cache_key
                continuation_reason = cursor_state or continuation_reason
        if top_frame_id is None and frame_path:
            top_frame_id = frame_path[-1].get("frameId")
            top_frame_node_id = frame_path[-1].get("nodeId") or top_frame_node_id
            top_frame_prefix_cache_key = frame_path[-1].get("prefixCacheKey")
            continuation_reason = frame_path[-1].get("cursorState") or continuation_reason
    continuation_reason = continuation_reason or resume_path or restart_trigger
    rework_reason: str | None = None
    if transition_outcome in {"continue-sibling-after-failure", "bubble-parent-after-failure", "failed-window-overflow", "failed"}:
        rework_reason = restart_trigger or continuation_reason or transition_outcome
    elif restart_trigger:
        rework_reason = restart_trigger
    return {
        "frameCount": len(frame_path),
        "activePathNodeIds": active_path_node_ids,
        "activePathFrameIds": active_path_frame_ids,
        "topFrameId": top_frame_id,
        "topFrameNodeId": top_frame_node_id,
        "topFramePrefixCacheKey": top_frame_prefix_cache_key,
        "continuationReason": continuation_reason,
        "reworkReason": rework_reason,
        "approvalStop0_1": 1 if transition_outcome == "awaiting-approval" else 0,
        "childBubble0_1": 1 if transition_outcome in {"bubble-parent", "bubble-parent-after-failure", "continue-sibling", "continue-sibling-after-failure"} else 0,
        "mixedOutcome0_1": 1 if child_status_counts.get("completed", 0) > 0 and child_status_counts.get("failed", 0) > 0 else 0,
        "childStatusCounts": child_status_counts,
        "recentChildCompletionSummaries": recent_child_completion_summaries[-6:],
        "framePath": frame_path,
    }
def _build_window_execution_record(
    *,
    task,
    run,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    runtime_metrics: dict[str, Any],
    current_context: list[dict[str, Any]],
    pre_retrieval_context: list[dict[str, Any]] | None = None,
    protected_items: list[dict[str, Any]] | None = None,
    llm_result: dict[str, Any] | None = None,
    memory_tag_write_result: dict[str, Any] | None = None,
    transition_stage: str,
    transition_outcome: str,
    resume_path: str | None = None,
    restart_trigger: str | None = None,
    source_snapshot_id: str | None = None,
    target_snapshot_id: str | None = None,
    next_window_index: int | None = None,
    rehydration_result: dict[str, Any] | None = None,
    created_node_id: str | None = None,
) -> dict[str, Any]:
    takeover_protocol = _coerce_takeover_protocol(request.get("takeoverProtocol"))
    work_tree = takeover_protocol.work_tree if takeover_protocol is not None else None
    pointer_state = _runtime_pointer_state(str(task.id), str(run.id), request)
    memory_state = _window_execution_memory_state(request)
    assistant_text = str((llm_result or {}).get("assistantText") or "")
    memory_tag_write_result = memory_tag_write_result or {}
    protected_ref_ids = _normalize_entity_ids(protected_items)
    response_requirements_digest = _stable_digest(request.get("responseRequirements"))
    restart_message = request.get("restartMessage") or task.restart_message or root_mount.get("resumeMessage")
    restart_message_digest = _stable_digest(restart_message)
    output_labels = _model_invocation_output_labels(request, memory_tag_write_result) if llm_result is not None else []
    work_context_stack_payload = pointer_state.get("workContextStack") if isinstance(pointer_state.get("workContextStack"), dict) else None
    cache_summary = _window_execution_cache_summary(llm_result)
    work_tree_debug = _window_execution_work_tree_debug(
        work_context_stack_payload,
        current_node_id=pointer_state.get("currentNodeId") or (work_tree.current_node_id if work_tree is not None else None),
        transition_outcome=transition_outcome,
        resume_path=resume_path,
        restart_trigger=restart_trigger,
    )
    state_fingerprint = _stable_digest(
        {
            "currentObjective": request.get("currentObjective"),
            "currentFocus": request.get("currentFocus"),
            "responseRequirementsDigest": response_requirements_digest,
            "restartMessageDigest": restart_message_digest,
            "workTreeCurrentNodeId": work_tree.current_node_id if work_tree is not None else None,
            "workTreeStatus": work_tree.status if work_tree is not None else None,
            "workTreeRecoveryAnchor": work_tree.recovery_anchor if work_tree is not None else None,
            "workingNodeAnnotation": pointer_state.get("workingNodeAnnotation"),
            "pcMemo": pointer_state.get("pcMemo"),
            "topFrameId": pointer_state.get("topFrameId"),
            "topFramePrefixCacheKey": work_tree_debug.get("topFramePrefixCacheKey"),
            "stackDigest": pointer_state.get("stackDigest"),
            "retrievalFingerprint": memory_state.get("retrievalFingerprint"),
            "protectedRefIds": protected_ref_ids,
        }
    )
    return {
        "artifactKind": "window-execution-record",
        "taskId": task.id,
        "projectId": task.project_id,
        "runId": run.id,
        "agentRunId": run.id,
        "invocationId": str(((llm_result or {}).get("invocation") or {}).get("id") or "").strip() or None,
        "createdAt": utc_now().isoformat(),
        "transitionStage": transition_stage,
        "transitionOutcome": transition_outcome,
        "resumePath": resume_path,
        "sourceSnapshotId": source_snapshot_id,
        "targetSnapshotId": target_snapshot_id,
        "nextWindowIndex": next_window_index,
        "restartTrigger": restart_trigger,
        "transitionStage": transition_stage,
        "transitionOutcome": transition_outcome,
        "windowIndex": max(_int_metric(runtime_metrics.get("windowIndex"), 1), 1),
        "restartCount": max(_int_metric(runtime_metrics.get("restartCount"), 0), 0),
        "effectiveContextWindow": max(_int_metric(runtime_metrics.get("effectiveContextWindow"), 0), 0),
        "windowRestartThreshold": max(_int_metric(runtime_metrics.get("windowRestartThreshold"), 0), 0),
        "windowSpanTokens": max(_int_metric(runtime_metrics.get("windowSpanTokens"), 0), 0),
        "cumulativeWindowSpanTokens": max(_int_metric(runtime_metrics.get("cumulativeWindowSpanTokens"), 0), 0),
        "carryForwardLossCount": max(_int_metric(runtime_metrics.get("carryForwardLossCount"), 0), 0),
        "currentObjective": str(request.get("currentObjective") or task.current_objective or task.goal or "").strip() or None,
        "currentFocus": str(request.get("currentFocus") or task.current_focus or "").strip() or None,
        "taskObjective": str(request.get("taskObjective") or task.current_objective or task.goal or "").strip() or None,
        "responseRequirementsDigest": response_requirements_digest,
        "restartMessageDigest": restart_message_digest,
        "currentContextCount": len([item for item in current_context if isinstance(item, dict)]),
        "currentContextTokenEstimate": _estimate_context_tokens(current_context),
        "currentContextTitlesPreview": _window_execution_titles_preview(current_context),
        "preRetrievalContextCount": len([item for item in (pre_retrieval_context or []) if isinstance(item, dict)]),
        "preRetrievalContextTokenEstimate": _estimate_context_tokens(pre_retrieval_context or []),
        "protectedRefIds": protected_ref_ids,
        "currentNodeId": pointer_state.get("currentNodeId") or (work_tree.current_node_id if work_tree is not None else None),
        "workTreeCurrentNodeId": work_tree.current_node_id if work_tree is not None else None,
        "workTreeStatus": work_tree.status if work_tree is not None else None,
        "workTreeRecoveryAnchor": work_tree.recovery_anchor if work_tree is not None else None,
        "workingNodeAnnotation": pointer_state.get("workingNodeAnnotation"),
        "pcMemo": pointer_state.get("pcMemo"),
        "topFrameId": pointer_state.get("topFrameId"),
        "topFramePrefixCacheKey": work_tree_debug.get("topFramePrefixCacheKey"),
        "stackDigest": pointer_state.get("stackDigest"),
        "memoryRetrievalState": memory_state,
        "cacheSummary": cache_summary,
        "workTreeDebug": work_tree_debug,
        "memoryTagWrites": {
            "detectedCount": max(_int_metric(memory_tag_write_result.get("detectedCount"), 0), 0),
            "appliedCount": len([item for item in memory_tag_write_result.get("applied") or [] if isinstance(item, dict)]),
            "blockedCount": len([item for item in memory_tag_write_result.get("blocked") or [] if isinstance(item, dict)]),
        },
        "llm": {
            "selectedModel": str((((llm_result or {}).get("invocation") or {}).get("resolvedModel") or run.selected_model or "")).strip() or None,
            "selectedProvider": str((((llm_result or {}).get("invocation") or {}).get("resolvedProvider") or run.selected_provider or "")).strip() or None,
            "assistantTextSummary": _assistant_text_summary(assistant_text),
            "finishReason": str((llm_result or {}).get("finishReason") or "").strip() or None,
            "mode": str((llm_result or {}).get("status") or (llm_result or {}).get("mode") or "").strip() or None,
            "toolExecutionCount": len([item for item in (llm_result or {}).get("toolExecutions") or [] if isinstance(item, dict)]),
            "planningStub0_1": 1 if _looks_like_planning_stub(assistant_text) else 0,
            "outputLabels": output_labels,
        },
        "rehydratedSummary": [
            str(item)
            for item in ((rehydration_result or {}).get("summaries") or [])
            if str(item).strip()
        ],
        "createdExecutionNodeId": created_node_id,
        "stateFingerprint": state_fingerprint,
    }
def _persist_window_execution_artifact(
    session,
    *,
    task,
    run,
    record: dict[str, Any],
) -> dict[str, Any]:
    workspace_root = resolve_workspace_root()
    artifact_dir = ensure_state_subdir("runtime/window-executions", workspace_root)
    artifact_path = artifact_dir / f"{task.id}-{run.id}.json"
    write_json(artifact_path, record)
    artifact_ref = ExternalRef(type="file", locator=relative_workspace_path(artifact_path, workspace_root))
    history_ref_payload = None
    invocation_id = str(record.get("invocationId") or "").strip()
    if invocation_id:
        history_dir = ensure_state_subdir("runtime/window-executions/by-invocation", workspace_root)
        history_path = history_dir / f"{invocation_id}.json"
        write_json(history_path, record)
        history_ref_payload = ExternalRef(type="file", locator=relative_workspace_path(history_path, workspace_root)).model_dump(mode="json")
    event = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="window-execution",
        aggregate_id=run.id,
        event_type="runtime.window-execution.persisted",
        locator=f"agent-runtime/runtime/window-executions/{task.id}/{run.id}",
    )
    return {
        "runId": run.id,
        "artifactRef": artifact_ref.model_dump(mode="json"),
        "historyRef": history_ref_payload,
        "record": record,
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }

__all__ = [name for name in globals() if not name.startswith("__")]
