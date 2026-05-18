import json
import logging
import re
from hashlib import sha1

from ._common import *  # noqa: F403,F401
from .root_mount import *  # noqa: F403,F401
from .snapshot import *  # noqa: F403,F401
from .execution_control import *  # noqa: F403,F401
from .takeover import *  # noqa: F403,F401
from ..contracts import RuntimeMetricsSnapshot
from ..llm_runtime import SafeShutdownInterrupt
from .shutdown_control import is_shutdown_requested as _is_shutdown_requested
from .snapshot import save_pending_tool_calls_snapshot

_logger = logging.getLogger(__name__)

_MEMORY_WRITE_TAG_PATTERN = re.compile(
    r"<memory-write(?P<attrs>[^>]*)>(?P<content>.*?)</memory-write>",
    re.IGNORECASE | re.DOTALL,
)
_MEMORY_WRITE_ATTR_PATTERN = re.compile(
    r"(?P<name>[A-Za-z][A-Za-z0-9_-]*)\s*=\s*(?P<quote>[\"'])(?P<value>.*?)(?P=quote)",
    re.DOTALL,
)


def _estimate_context_text_tokens(text: str) -> int:
    compact = " ".join(str(text).split())
    return max(1, len(compact) // 4) if compact else 0


def _estimate_context_item_tokens(item: dict[str, Any]) -> int:
    parts = [
        str(item.get(key) or "")
        for key in ("title", "content", "summary", "normalizedText", "excerpt", "note")
        if item.get(key)
    ]
    return sum(_estimate_context_text_tokens(part) for part in parts)


def _estimate_context_tokens(items: list[dict[str, Any]]) -> int:
    return sum(_estimate_context_item_tokens(item) for item in items if isinstance(item, dict))


def _append_context_length_observation(
    observations: list[dict[str, Any]],
    *,
    phase: str,
    source: str,
    items: list[dict[str, Any]],
    trigger: str | None = None,
) -> None:
    observation: dict[str, Any] = {
        "phase": phase,
        "source": source,
        "estimatedTokens": _estimate_context_tokens(items),
        "itemCount": len(items),
    }
    if trigger:
        observation["trigger"] = trigger
    observations.append(observation)


def _int_metric(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _float_metric(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _runtime_metrics(task, request: dict[str, Any]) -> dict[str, Any]:
    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    effective_context_window = max(
        _int_metric(request.get("effectiveContextWindow"), _int_metric(request_metrics.get("effectiveContextWindow"), 0)),
        0,
    )
    restart_ratio = _float_metric(request.get("windowRestartRatio"), 0.75)
    restart_ratio = min(max(restart_ratio, 0.1), 1.0)
    threshold = max(
        _int_metric(request.get("windowRestartThreshold"), _int_metric(request_metrics.get("windowRestartThreshold"), 0)),
        0,
    )
    if threshold <= 0 and effective_context_window > 0:
        threshold = max(1, min(effective_context_window, int(effective_context_window * restart_ratio)))

    return {
        "windowIndex": max(
            _int_metric(request.get("windowIndex"), _int_metric(request_metrics.get("windowIndex"), getattr(task, "window_index", 1))),
            1,
        ),
        "restartCount": max(
            _int_metric(request.get("restartCount"), _int_metric(request_metrics.get("restartCount"), getattr(task, "restart_count", 0))),
            0,
        ),
        "compressionCount": max(_int_metric(request.get("compressionCount"), _int_metric(request_metrics.get("compressionCount"), 0)), 0),
        "cumulativeWindowSpanTokens": max(
            _int_metric(
                request.get("cumulativeWindowSpanTokens"),
                _int_metric(request_metrics.get("cumulativeWindowSpanTokens"), getattr(task, "cumulative_window_span_tokens", 0)),
            ),
            0,
        ),
        "carryForwardLossCount": max(
            _int_metric(
                request.get("carryForwardLossCount"),
                _int_metric(request_metrics.get("carryForwardLossCount"), getattr(task, "carry_forward_loss_count", 0)),
            ),
            0,
        ),
        "forcedWindowRestartBudget": max(
            _int_metric(request.get("forcedWindowRestartBudget"), _int_metric(request_metrics.get("forcedWindowRestartBudget"), 0)),
            0,
        ),
        "effectiveContextWindow": effective_context_window,
        "windowRestartRatio": restart_ratio,
        "windowRestartThreshold": threshold,
        "windowSpanTokens": max(_int_metric(request_metrics.get("windowSpanTokens"), 0), 0),
    }


def _build_runtime_metrics_snapshot(
    *,
    runtime_metrics: dict[str, Any],
    llm_result: dict[str, Any],
) -> RuntimeMetricsSnapshot:
    """Build normalized runtime metrics snapshot for artifact persistence."""
    usage = llm_result.get("usage") if isinstance(llm_result.get("usage"), dict) else {}
    tool_executions = llm_result.get("toolExecutions") if isinstance(llm_result.get("toolExecutions"), list) else []
    tool_failures_count = sum(
        1
        for execution in tool_executions
        if isinstance(execution, dict) and not bool(execution.get("success"))
    )
    tool_round_count = len(
        [
            summary
            for summary in (llm_result.get("roundSummaries") or [])
            if isinstance(summary, dict)
        ]
    )
    return RuntimeMetricsSnapshot(
        windowIndex=max(_int_metric(runtime_metrics.get("windowIndex"), 1), 1),
        restartCount=max(_int_metric(runtime_metrics.get("restartCount"), 0), 0),
        totalTokensUsed=max(_int_metric(usage.get("totalTokens"), 0), 0),
        totalCostUsed=max(_float_metric(llm_result.get("costUsed"), 0.0), 0.0),
        cumulativeWindowSpanTokens=max(_int_metric(runtime_metrics.get("cumulativeWindowSpanTokens"), 0), 0),
        carryForwardLossCount=max(_int_metric(runtime_metrics.get("carryForwardLossCount"), 0), 0),
        toolRoundCount=tool_round_count,
        toolFailuresCount=tool_failures_count,
    )


def _persist_runtime_metrics_artifact(
    session,
    *,
    task,
    invocation_id: str,
    metrics_snapshot: RuntimeMetricsSnapshot,
) -> dict[str, Any]:
    """Persist runtime metrics to artifact file and emit a DB-backed runtime event."""
    workspace_root = resolve_workspace_root()
    metrics_dir = ensure_state_subdir("runtime/metrics", workspace_root)
    metrics_path = metrics_dir / f"{invocation_id}.json"
    payload = {
        "taskId": task.id,
        "projectId": task.project_id,
        "invocationId": invocation_id,
        "createdAt": utc_now().isoformat(),
        "snapshot": metrics_snapshot.model_dump(by_alias=True, mode="json"),
    }
    write_json(metrics_path, payload)
    metrics_ref = ExternalRef(type="file", locator=relative_workspace_path(metrics_path, workspace_root))
    event = _persist_runtime_event(
        session,
        project_id=task.project_id,
        aggregate_type="runtime-metrics",
        aggregate_id=invocation_id,
        event_type="runtime.metrics.persisted",
        locator=f"agent-runtime/runtime/metrics/{invocation_id}",
    )
    return {
        "invocationId": invocation_id,
        "metricsRef": metrics_ref.model_dump(mode="json"),
        "snapshot": metrics_snapshot.model_dump(by_alias=True, mode="json"),
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def _window_restart_trigger(request: dict[str, Any], runtime_metrics: dict[str, Any], effective_context: list[dict[str, Any]]) -> tuple[str | None, int]:
    window_span_tokens = _estimate_context_tokens(effective_context)
    if _int_metric(runtime_metrics.get("forcedWindowRestartBudget"), 0) > 0 and effective_context:
        return "forcedWindowRestartBudget", window_span_tokens
    if bool(request.get("forceWindowRestart")) and effective_context:
        return "forceWindowRestart", window_span_tokens
    effective_context_window = _int_metric(runtime_metrics.get("effectiveContextWindow"), 0)
    restart_threshold = _int_metric(runtime_metrics.get("windowRestartThreshold"), 0)
    if effective_context_window > 0 and restart_threshold > 0 and window_span_tokens >= restart_threshold:
        return "effectiveContextWindow", window_span_tokens
    return None, window_span_tokens


def _dedupe_memory_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            continue
        record_id = str(record.get("id") or "")
        dedupe_key = record_id or repr(sorted(record.items()))
        if dedupe_key in seen_ids:
            continue
        seen_ids.add(dedupe_key)
        deduped.append(record)
    return deduped


def _coerce_takeover_protocol(candidate: Any) -> TaskTakeoverProtocol | None:
    if isinstance(candidate, TaskTakeoverProtocol):
        return candidate
    if not isinstance(candidate, dict):
        return None
    try:
        return TaskTakeoverProtocol.model_validate(candidate)
    except Exception:
        return None


def _work_tree_node_id_from_request(request: dict[str, Any]) -> str | None:
    protocol = _coerce_takeover_protocol(request.get("takeoverProtocol"))
    if protocol is not None and protocol.work_tree is not None and protocol.work_tree.current_node_id is not None:
        return str(protocol.work_tree.current_node_id)
    candidate = request.get("workTreeNodeId")
    if candidate is None:
        return None
    normalized = str(candidate).strip()
    return normalized or None


def _assistant_text_summary(text: str, limit: int = 240) -> str | None:
    normalized = normalize_excerpt(" ".join(str(text).split()), limit)
    return normalized or None


def _model_invocation_output_labels(request: dict[str, Any], memory_tag_write_result: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in memory_tag_write_result.get("applied") or []:
        if not isinstance(item, dict):
            continue
        labels.append(f"memory-write:{item.get('status') or 'applied'}:{item.get('action') or 'create'}")
    memory_retrieval_state = request.get("memoryRetrievalState") if isinstance(request.get("memoryRetrievalState"), dict) else {}
    if memory_retrieval_state.get("reverseTraceMode"):
        labels.append("memory-retrieval:reverse-trace")
    work_tree_node_id = _work_tree_node_id_from_request(request)
    if work_tree_node_id is not None:
        labels.append(f"work-tree:{work_tree_node_id}")
    deduped: list[str] = []
    for label in labels:
        normalized = str(label).strip()
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped


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
    memory_state = _window_execution_memory_state(request)
    assistant_text = str((llm_result or {}).get("assistantText") or "")
    memory_tag_write_result = memory_tag_write_result or {}
    protected_ref_ids = _normalize_entity_ids(protected_items)
    response_requirements_digest = _stable_digest(request.get("responseRequirements"))
    restart_message = request.get("restartMessage") or task.restart_message or root_mount.get("resumeMessage")
    restart_message_digest = _stable_digest(restart_message)
    output_labels = _model_invocation_output_labels(request, memory_tag_write_result) if llm_result is not None else []
    state_fingerprint = _stable_digest(
        {
            "currentObjective": request.get("currentObjective"),
            "currentFocus": request.get("currentFocus"),
            "responseRequirementsDigest": response_requirements_digest,
            "restartMessageDigest": restart_message_digest,
            "workTreeCurrentNodeId": work_tree.current_node_id if work_tree is not None else None,
            "workTreeStatus": work_tree.status if work_tree is not None else None,
            "workTreeRecoveryAnchor": work_tree.recovery_anchor if work_tree is not None else None,
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
        "workTreeCurrentNodeId": work_tree.current_node_id if work_tree is not None else None,
        "workTreeStatus": work_tree.status if work_tree is not None else None,
        "workTreeRecoveryAnchor": work_tree.recovery_anchor if work_tree is not None else None,
        "memoryRetrievalState": memory_state,
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
        "record": record,
        "outboxRecord": event.model_dump(by_alias=True, mode="json"),
    }


def _context_parent_for_root_branch(root_mount: dict[str, Any], execution_root_id: str, root_branch: str) -> str | None:
    if root_branch == "identity":
        refs = root_mount.get("identityRefs") or []
        return str(refs[0].get("id")) if refs else None
    if root_branch == "execution":
        return execution_root_id
    refs = root_mount.get("contextRefs") or []
    return str(refs[0].get("id")) if refs else None


def _target_parent_for_root_branch(
    task,
    *,
    root_mount: dict[str, Any],
    execution_root_id: str,
    root_branch: str,
    target_branch_id: str,
) -> str | None:
    if target_branch_id == task.branch_id:
        return _context_parent_for_root_branch(root_mount, execution_root_id, root_branch)
    return str(new_id("node", task.project_id, target_branch_id, root_branch, stable=True))


def _materialize_runtime_context_items(
    session,
    *,
    task,
    current_context: list[dict[str, Any]],
    root_mount: dict[str, Any],
    execution_root_id: str,
    window_index: int,
    source_work_tree_node_id: str | None,
    source_run_id: str | None,
) -> list[str]:
    if not current_context:
        return []

    repository = NodeRepository(session)
    actor = {"type": "module", "id": "runtime-kernel"}
    materialized_node_ids: list[str] = []

    for index, item in enumerate(current_context, start=1):
        if not isinstance(item, dict):
            continue
        if str(item.get("kind") or "") in {"retrieval-summary", "carry-forward-package"}:
            continue
        ref = item.get("ref") if isinstance(item.get("ref"), dict) else None
        if ref and ref.get("kind") == "node" and ref.get("id"):
            materialized_node_ids.append(str(ref["id"]))
            continue

        root_branch = str(item.get("rootBranch") or item.get("mode") or "context")
        if root_branch not in {"identity", "context", "execution"}:
            root_branch = "context"
        parent_id = _context_parent_for_root_branch(root_mount, execution_root_id, root_branch)
        if not parent_id:
            continue

        title = str(item.get("title") or item.get("kind") or f"runtime-context-{index}").strip()
        raw_content = str(
            item.get("content")
            or item.get("summary")
            or item.get("normalizedText")
            or item.get("excerpt")
            or ""
        ).strip()
        if not title or not raw_content:
            continue

        node_id = str(item.get("memoryNodeId") or new_id("runtimectx", task.id, item.get("id") or title, stable=True))
        content = normalize_excerpt(raw_content, 200)
        existing_node = repository.get_node(node_id)
        if existing_node is None:
            repository.create_node(
                {
                    "id": node_id,
                    "projectId": task.project_id,
                    "spaceId": task.space_id,
                    "branchId": task.branch_id,
                    "parentId": parent_id,
                    "rootBranch": root_branch,
                    "nodeType": "temporary",
                    "status": "temporary",
                    "title": title,
                    "content": content,
                    "detailLevel": 2,
                    "importance": float(item.get("importance", 0.6)),
                    "stability": 0.5,
                    "forgetRate": 0.25,
                    "feedforwardScore": 0.7,
                    "accessScore": 0.0,
                    "activityK": 0.4,
                    "floatScore": 0.3,
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "sourceRunId": source_run_id,
                    "createdBy": actor,
                    "updatedBy": actor,
                    "changeReason": "runtime-context-materialization",
                }
            )
        else:
            repository.append_version(
                node_id,
                {
                    "title": title,
                    "content": content,
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "sourceRunId": source_run_id,
                    "changeReason": "runtime-context-materialization",
                    "updatedBy": actor,
                }
            )
        materialized_node_ids.append(node_id)

    return materialized_node_ids


def _context_item_from_retrieved_node(node_payload: dict[str, Any]) -> dict[str, Any]:
    ref = node_payload.get("ref") if isinstance(node_payload.get("ref"), dict) else None
    content_lines = [str(node_payload.get("content") or "")]
    child_names = [str(item) for item in node_payload.get("childNames") or [] if item]
    related_names = [str(item) for item in node_payload.get("relatedNames") or [] if item]
    if child_names:
        content_lines.append("Children: " + ", ".join(child_names[:8]))
    if related_names:
        content_lines.append("Related: " + ", ".join(related_names[:8]))
    return {
        "id": str((ref or {}).get("id") or node_payload.get("id") or new_id("retrieved-node", node_payload.get("title") or "context")),
        "ref": ref,
        "title": str(node_payload.get("title") or "memory-node"),
        "content": "\n".join(part for part in content_lines if part).strip(),
        "rootBranch": str(node_payload.get("rootBranch") or "context"),
    }


def _memory_retrieval_token_budget(request: dict[str, Any]) -> int | None:
    explicit_budget = max(_int_metric(request.get("maxRetainedTokens"), 0), 0)
    if explicit_budget > 0:
        return explicit_budget

    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    effective_context_window = max(
        _int_metric(request.get("effectiveContextWindow"), _int_metric(request_metrics.get("effectiveContextWindow"), 0)),
        0,
    )
    restart_ratio = _float_metric(request.get("windowRestartRatio"), _float_metric(request_metrics.get("windowRestartRatio"), 0.75))
    restart_ratio = min(max(restart_ratio, 0.1), 1.0)
    restart_threshold = max(
        _int_metric(request.get("windowRestartThreshold"), _int_metric(request_metrics.get("windowRestartThreshold"), 0)),
        0,
    )
    if restart_threshold <= 0 and effective_context_window > 0:
        restart_threshold = max(1, min(effective_context_window, int(effective_context_window * restart_ratio)))

    if restart_threshold > 0:
        return max(32, restart_threshold - 8)
    if effective_context_window > 0:
        return max(32, effective_context_window - 8)
    return None


def _trim_context_items_to_token_budget(context_items: list[dict[str, Any]], token_budget: int | None) -> list[dict[str, Any]]:
    if token_budget is None or token_budget <= 0 or not context_items:
        return context_items

    trimmed_items = [dict(item) for item in context_items if isinstance(item, dict)]
    while len(trimmed_items) > 1 and _estimate_context_tokens(trimmed_items) > token_budget:
        trimmed_items.pop()

    if trimmed_items and _estimate_context_tokens(trimmed_items) > token_budget:
        summary_item = dict(trimmed_items[0])
        summary_content = str(summary_item.get("content") or "")
        target_chars = max(64, token_budget * 4)
        while summary_content and _estimate_context_tokens([summary_item]) > token_budget and len(summary_content) > 64:
            summary_content = normalize_excerpt(summary_content, target_chars)
            summary_item["content"] = summary_content
            target_chars = max(64, len(summary_content) // 2)
        trimmed_items[0] = summary_item

    return trimmed_items


def _should_trim_retrieved_context(current_context: list[dict[str, Any]]) -> bool:
    return any(str(item.get("kind") or "") == "carry-forward-package" for item in current_context if isinstance(item, dict))


def _parse_memory_write_tag_attributes(attribute_text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for match in _MEMORY_WRITE_ATTR_PATTERN.finditer(attribute_text):
        attributes[str(match.group("name") or "").strip().lower()] = str(match.group("value") or "").strip()
    return attributes


def _normalize_memory_tag_root_branch(value: str | None) -> str:
    candidate = str(value or "context").strip().lower()
    return candidate if candidate in {"identity", "context", "execution"} else "context"


def _normalize_memory_tag_action(value: str | None, *, has_node_id: bool) -> str:
    candidate = str(value or ("append" if has_node_id else "create")).strip().lower()
    return candidate if candidate in {"create", "append", "replace"} else ("append" if has_node_id else "create")


def _extract_assistant_memory_write_tags(assistant_text: str, *, enabled: bool) -> dict[str, Any]:
    if not enabled:
        return {
            "cleanAssistantText": str(assistant_text or "").strip(),
            "writes": [],
            "blocked": [],
            "detectedCount": 0,
        }

    parsed_writes: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []

    def _replace(match: re.Match[str]) -> str:
        raw_tag = str(match.group(0) or "")
        attributes = _parse_memory_write_tag_attributes(str(match.group("attrs") or ""))
        content = str(match.group("content") or "").strip()
        node_id = str(attributes.get("nodeid") or "").strip()
        title = str(attributes.get("title") or "").strip()
        action_raw = str(attributes.get("action") or "").strip().lower()
        if not content:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "empty-content",
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        if not node_id and not title:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "missing-title-or-nodeId",
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        if action_raw and action_raw not in {"create", "append", "replace"}:
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "invalid-action",
                    "action": action_raw,
                    "tagPreview": normalize_excerpt(raw_tag, 160),
                }
            )
            return ""
        parsed_writes.append(
            {
                "rawTag": raw_tag,
                "title": title,
                "content": content,
                "nodeId": node_id or None,
                "action": _normalize_memory_tag_action(attributes.get("action"), has_node_id=bool(node_id)),
                "rootBranch": _normalize_memory_tag_root_branch(attributes.get("rootbranch")),
                "importance": min(max(_float_metric(attributes.get("importance"), 0.72), 0.0), 1.0),
                "detailLevel": max(_int_metric(attributes.get("detaillevel"), 2), 1),
                "targetSpaceId": str(attributes.get("spaceid") or "").strip() or None,
                "targetBranchId": str(attributes.get("branchid") or "").strip() or None,
            }
        )
        return ""

    stripped = _MEMORY_WRITE_TAG_PATTERN.sub(_replace, assistant_text)
    clean_text = re.sub(r"\n{3,}", "\n\n", stripped).strip()
    return {
        "cleanAssistantText": clean_text,
        "writes": parsed_writes,
        "blocked": blocked,
        "detectedCount": len(parsed_writes) + len(blocked),
    }


def _assistant_memory_write_annotation(
    *,
    task,
    run,
    invocation_id: str,
    write: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    return {
        "id": new_id("srcann", task.id, run.id, "assistant-memory-tag", index, stable=True),
        "sourceType": "assistant-memory-tag",
        "sourceRef": {
            "type": "package-entry",
            "locator": f"agent-runtime/runtime/model-invocations/{invocation_id}#memory-write-{index}",
        },
        "excerpt": normalize_excerpt(str(write.get("rawTag") or ""), 240),
        "inferenceSummary": f"Assistant output memory tag ({write.get('action') or 'create'}) was applied at a safe stop.",
        "confidence": 0.95,
        "createdBy": {"type": "module", "id": "runtime-kernel"},
    }


def _apply_memory_write_annotations(
    node_repository: NodeRepository,
    *,
    node_id: str,
    task,
    branch_id: str,
    annotations: list[dict[str, Any]],
) -> None:
    for index, annotation in enumerate([item for item in annotations if isinstance(item, dict)], start=1):
        node_repository.add_source_annotation(
            "node",
            node_id,
            {
                "id": annotation.get("id") or new_id("srcann", node_id, index, stable=True),
                "projectId": task.project_id,
                "branchId": branch_id,
                "sourceType": annotation.get("sourceType") or "memory",
                "sourceRef": annotation.get("sourceRef"),
                "excerpt": annotation.get("excerpt"),
                "inferenceSummary": annotation.get("inferenceSummary") or annotation.get("summary"),
                "evidenceRefs": annotation.get("evidenceRefs") or [],
                "confidence": float(annotation.get("confidence", 0.85)),
                "createdBy": annotation.get("createdBy") or {"type": "module", "id": "runtime-kernel"},
            },
        )


def _apply_assistant_memory_write_tags(
    session,
    *,
    task,
    run,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    execution_root_id: str,
    llm_result: dict[str, Any],
    execution_actor_id: str,
) -> dict[str, Any]:
    memory_tag_writes_enabled = bool(request.get("memoryWriteTagsEnabled", True))
    parsed = _extract_assistant_memory_write_tags(
        str(llm_result.get("assistantText") or ""),
        enabled=memory_tag_writes_enabled,
    )
    llm_result["assistantText"] = parsed["cleanAssistantText"]
    writes = [item for item in parsed["writes"] if isinstance(item, dict)]
    work_tree_node_id = _work_tree_node_id_from_request(request)
    runtime_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    window_index = max(_int_metric(runtime_metrics.get("windowIndex"), _int_metric(request.get("windowIndex"), 1)), 1)
    if not writes:
        return {
            "detectedCount": int(parsed["detectedCount"]),
            "cleanAssistantText": str(llm_result.get("assistantText") or ""),
            "applied": [],
            "blocked": [dict(item) for item in parsed["blocked"] if isinstance(item, dict)],
            "events": [],
        }

    node_repository = NodeRepository(session)
    applied: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = [dict(item) for item in parsed["blocked"] if isinstance(item, dict)]
    events: list[dict[str, Any]] = []
    active_modules = root_mount.get("activeCapabilities") or None
    subject = request.get("subject") or (f"profile:{task.owner_profile_id}" if task.owner_profile_id else None)
    invocation_id = str((llm_result.get("invocation") or {}).get("id") or run.id)

    for index, write in enumerate(writes, start=1):
        try:
            node_id = str(write.get("nodeId") or "").strip() or None
            existing_node = node_repository.get_node(node_id) if node_id is not None else None
            if node_id is not None and existing_node is None:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-node",
                        "nodeId": node_id,
                        "action": write.get("action"),
                    }
                )
                continue

            resolved_root_branch = str(existing_node.root_branch) if existing_node is not None else str(write.get("rootBranch") or "context")
            target_space_id = str(write.get("targetSpaceId") or (existing_node.space_id if existing_node is not None else task.space_id))
            target_branch_id = str(write.get("targetBranchId") or (existing_node.branch_id if existing_node is not None else task.branch_id))
            title = str(write.get("title") or (existing_node.title if existing_node is not None else "")).strip()
            if existing_node is not None:
                if str(write.get("action")) == "replace":
                    content = str(write.get("content") or "").strip()
                else:
                    existing_content = str(existing_node.content or "").strip()
                    new_fragment = str(write.get("content") or "").strip()
                    content = "\n".join(part for part in [existing_content, new_fragment] if part)
            else:
                content = str(write.get("content") or "").strip()

            candidate_parent_id = (
                str(existing_node.parent_id) if existing_node is not None and existing_node.parent_id is not None else None
            )
            if candidate_parent_id is None:
                candidate_parent_id = _target_parent_for_root_branch(
                    task,
                    root_mount=root_mount,
                    execution_root_id=execution_root_id,
                    root_branch=resolved_root_branch,
                    target_branch_id=target_branch_id,
                )
            if candidate_parent_id is None:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "missing-parent",
                        "rootBranch": resolved_root_branch,
                        "title": title,
                    }
                )
                continue

            validation_payload = {
                "taskId": task.id,
                "projectId": task.project_id,
                "hostSpaceId": task.space_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "ownerProfileId": task.owner_profile_id,
                "subject": subject,
                "relation": "write",
                "targetSpaceId": target_space_id,
                "targetBranchId": target_branch_id,
                "nodePayload": {"title": title, "content": content},
                "candidateNodes": [
                    {
                        "id": node_id or new_id("candnode", task.id, run.id, "assistant-memory-tag", index, stable=True),
                        "title": title,
                        "content": content,
                        "parentId": candidate_parent_id,
                        "rootBranch": resolved_root_branch,
                        "nodeType": str(existing_node.node_type) if existing_node is not None else "detail",
                    }
                ],
                "candidateEdges": [],
                "rootMount": root_mount,
            }
            write_validation = validate_memory_write(validation_payload, module_ids=active_modules)
            if not write_validation["allowed"]:
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "validation-failed",
                        "title": title,
                        "nodeId": node_id,
                        "action": write.get("action"),
                        "blockers": list(write_validation.get("blockers") or []),
                    }
                )
                continue

            resolved_space_id = str(write_validation.get("targetSpaceId") or target_space_id)
            resolved_branch_id = str(write_validation.get("targetBranchId") or target_branch_id)
            if existing_node is not None and (
                resolved_space_id != str(existing_node.space_id) or resolved_branch_id != str(existing_node.branch_id)
            ):
                blocked.append(
                    {
                        "status": "blocked",
                        "reason": "retarget-existing-node-unsupported",
                        "title": title,
                        "nodeId": node_id,
                        "action": write.get("action"),
                    }
                )
                continue

            annotations = [
                _assistant_memory_write_annotation(
                    task=task,
                    run=run,
                    invocation_id=invocation_id,
                    write=write,
                    index=index,
                ),
                *[annotation for annotation in write_validation.get("annotations") or [] if isinstance(annotation, dict)],
            ]

            if existing_node is None:
                if resolved_space_id != task.space_id or resolved_branch_id != task.branch_id:
                    WorkspaceBootstrapRepository(session).ensure_branch_workspace(
                        branch_id=resolved_branch_id,
                        project_id=task.project_id,
                        space_id=resolved_space_id,
                    )
                parent_id = _target_parent_for_root_branch(
                    task,
                    root_mount=root_mount,
                    execution_root_id=execution_root_id,
                    root_branch=resolved_root_branch,
                    target_branch_id=resolved_branch_id,
                )
                if parent_id is None:
                    blocked.append(
                        {
                            "status": "blocked",
                            "reason": "missing-parent",
                            "rootBranch": resolved_root_branch,
                            "title": title,
                        }
                    )
                    continue
                created_node = node_repository.create_node(
                    {
                        "projectId": task.project_id,
                        "spaceId": resolved_space_id,
                        "branchId": resolved_branch_id,
                        "parentId": parent_id,
                        "rootBranch": resolved_root_branch,
                        "nodeType": "detail",
                        "title": title,
                        "content": content,
                        "detailLevel": int(write.get("detailLevel") or 2),
                        "importance": float(write.get("importance", 0.72)),
                        "windowIndex": window_index,
                        "sourceWorkTreeNodeId": work_tree_node_id,
                        "createdBy": {"type": "agent", "id": execution_actor_id},
                        "updatedBy": {"type": "agent", "id": execution_actor_id},
                        "changeReason": "assistant-output-memory-tag",
                    }
                )
                _apply_memory_write_annotations(
                    node_repository,
                    node_id=created_node.id,
                    task=task,
                    branch_id=resolved_branch_id,
                    annotations=annotations,
                )
                event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="node",
                    aggregate_id=created_node.id,
                    event_type="node.created",
                    locator=f"agent-runtime/tasks/{task.id}/memory-tag-writes/{created_node.id}",
                )
                applied.append(
                    {
                        "status": "created",
                        "nodeId": created_node.id,
                        "title": created_node.title,
                        "rootBranch": created_node.root_branch,
                        "action": write.get("action"),
                    }
                )
                events.append(event.model_dump(by_alias=True, mode="json"))
                continue

            node_repository.append_version(
                existing_node.id,
                {
                    "title": title,
                    "content": content,
                    "importance": float(write.get("importance", existing_node.importance)),
                    "windowIndex": window_index,
                    "sourceWorkTreeNodeId": work_tree_node_id,
                    "changeReason": "assistant-output-memory-tag",
                    "updatedBy": {"type": "agent", "id": execution_actor_id},
                },
            )
            _apply_memory_write_annotations(
                node_repository,
                node_id=existing_node.id,
                task=task,
                branch_id=existing_node.branch_id,
                annotations=annotations,
            )
            event = _persist_runtime_event(
                session,
                project_id=task.project_id,
                aggregate_type="node",
                aggregate_id=existing_node.id,
                event_type="node.updated",
                locator=f"agent-runtime/tasks/{task.id}/memory-tag-writes/{existing_node.id}",
            )
            applied.append(
                {
                    "status": "updated",
                    "nodeId": existing_node.id,
                    "title": title,
                    "rootBranch": existing_node.root_branch,
                    "action": write.get("action"),
                }
            )
            events.append(event.model_dump(by_alias=True, mode="json"))
        except Exception as exc:  # noqa: BLE001
            blocked.append(
                {
                    "status": "blocked",
                    "reason": "unexpected-error",
                    "title": str(write.get("title") or ""),
                    "nodeId": write.get("nodeId"),
                    "action": write.get("action"),
                    "detail": str(exc),
                }
            )

    return {
        "detectedCount": int(parsed["detectedCount"]),
        "cleanAssistantText": str(llm_result.get("assistantText") or ""),
        "applied": applied,
        "blocked": blocked,
        "events": events,
    }


__all__ = [name for name in globals() if not name.startswith("__")]


