import logging
import re

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
                _append_context_length_observation(
                    context_length_observations,
                    phase="beforeWindowRestart",
                    source="effectiveContext",
                    items=effective_context,
                    trigger=restart_trigger,
                )
                request["contextLengthObservations"] = [dict(item) for item in context_length_observations]
                restart_transition_started_at = perf_counter()
                source_window_span_tokens = max(window_span_tokens, _estimate_context_tokens(pre_retrieval_context))
                restart_state = _build_restart_snapshot_state(
                    task_id,
                    {
                        **request,
                        "projectId": task.project_id,
                        "branchId": task.branch_id,
                        "spaceId": task.space_id,
                        "agentRunId": run.id,
                        "currentContextState": effective_context,
                        "rootMountPreview": root_mount,
                        "restartMessage": request.get("restartMessage") or task.restart_message or f"Continue task {task.id} from the carry-forward package.",
                        "windowIndex": runtime_metrics["windowIndex"],
                        "restartCount": runtime_metrics["restartCount"],
                        "compressionCount": runtime_metrics["compressionCount"],
                        "cumulativeWindowSpanTokens": runtime_metrics["cumulativeWindowSpanTokens"],
                        "carryForwardLossCount": runtime_metrics["carryForwardLossCount"],
                        "forcedWindowRestartBudget": runtime_metrics["forcedWindowRestartBudget"],
                        "effectiveContextWindow": runtime_metrics["effectiveContextWindow"],
                        "windowRestartThreshold": runtime_metrics["windowRestartThreshold"],
                        "windowSpanTokens": source_window_span_tokens,
                        "protectedItems": protected_items,
                    },
                )
                restart_snapshot_summary: TaskSnapshotSummary = restart_state["snapshot"]
                task_repository.supersede_snapshots(task_id)
                task_repository.create_snapshot(restart_snapshot_summary)
                snapshot_created_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task-snapshot",
                    aggregate_id=restart_snapshot_summary.id,
                    event_type="task.snapshot.created",
                    locator=f"agent-runtime/tasks/{task_id}/snapshots/{restart_snapshot_summary.id}",
                )
                restart_request_locator = f"agent-runtime/tasks/{task.id}/restart-requests/{restart_snapshot_summary.id}"
                _cache_package_entry(
                    coordinator,
                    restart_request_locator,
                    {
                        "snapshotId": restart_snapshot_summary.id,
                        "resumeToken": restart_snapshot_summary.resume_token,
                        "sourceWindowIndex": runtime_metrics["windowIndex"],
                        "targetWindowIndex": restart_state["runtimeMetrics"]["windowIndex"],
                        "effectiveContextWindow": restart_state["runtimeMetrics"]["effectiveContextWindow"],
                        "windowRestartThreshold": restart_state["runtimeMetrics"]["windowRestartThreshold"],
                        "windowSpanTokens": restart_state["runtimeMetrics"]["windowSpanTokens"],
                    },
                )
                restart_requested_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task",
                    aggregate_id=task.id,
                    event_type="context.restart.requested",
                    locator=restart_request_locator,
                )
                queued_work_item = {
                    "activity": "core.agent.main.execute",
                    "taskId": task_id,
                    "command": "resume",
                    "requestedAt": utc_now().isoformat(),
                    "payload": {
                        "resumeToken": restart_snapshot_summary.resume_token,
                        "parentRunId": run.id,
                    },
                }
                queue_depth = coordinator.enqueue_job(AGENT_RUNTIME_QUEUE, queued_work_item)
                task = task_repository.update_task(
                    task_id,
                    {
                        "status": "restarting",
                        "pauseRequested": False,
                        "activeSnapshotId": restart_snapshot_summary.id,
                        "lastSafeStopAt": utc_now(),
                        "resumeMessage": restart_snapshot_summary.resume_message,
                        "restartMessage": None,
                        "currentFocus": "window-restart-handoff",
                        "windowIndex": restart_state["runtimeMetrics"]["windowIndex"],
                        "restartCount": restart_state["runtimeMetrics"]["restartCount"],
                        "cumulativeWindowSpanTokens": restart_state["runtimeMetrics"]["cumulativeWindowSpanTokens"],
                        "carryForwardLossCount": restart_state["runtimeMetrics"]["carryForwardLossCount"],
                    },
                )
                run = task_repository.update_agent_run(
                    run.id,
                    {
                        "status": "aborted",
                        "windowIndex": runtime_metrics["windowIndex"],
                        "restartCount": restart_state["runtimeMetrics"]["restartCount"],
                        "cumulativeWindowSpanTokens": restart_state["runtimeMetrics"]["cumulativeWindowSpanTokens"],
                    },
                )
                runtime_timings["restartTransitionMs"] = _elapsed_ms(restart_transition_started_at)
                runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
                return {
                    "status": "restarting",
                    "task": task.model_dump(by_alias=True, mode="json"),
                    "run": run.model_dump(by_alias=True, mode="json"),
                    "routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
                    "rootMount": root_mount,
                    "snapshot": restart_snapshot_summary.model_dump(by_alias=True, mode="json"),
                    "queuedWorkItem": queued_work_item,
                    "queueDepth": queue_depth,
                    "pruning": pruning_result,
                    "pruningEvents": pruning_events,
                    "runtimeMetrics": restart_state["runtimeMetrics"],
                    "outboxRecords": {
                        "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                        "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                        "snapshotCreated": snapshot_created_event.model_dump(by_alias=True, mode="json"),
                        "contextRestartRequested": restart_requested_event.model_dump(by_alias=True, mode="json"),
                    },
                    "resume": resume_event_payload,
                    "rehydration": rehydration_result,
                    "runtimeTimings": dict(runtime_timings),
                }
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

            # Re-read task to detect pause requests that arrived during execution
            # (the local `task` variable may be stale if request_task_pause was called concurrently)
            # Expire the identity-map entry so SQLAlchemy fetches a fresh row from the DB.
            session.expire_all()
            fresh_task = task_repository.get_task(task_id)
            if fresh_task is not None:
                task = fresh_task

            if task.pause_requested or bool(request.get("pauseAfterWrite", False)):
                pause_transition_started_at = perf_counter()
                pause_resume_message = request.get("resumeMessage") or task.resume_message or f"Resume task {task.id} after the last safe stop."
                pending_write_refs = [
                    {"kind": "node", "id": created_node.id},
                    *[
                        {"kind": "node", "id": str(item.get("nodeId"))}
                        for item in memory_tag_write_result.get("applied") or []
                        if isinstance(item, dict) and item.get("nodeId") is not None
                    ],
                ]
                pause_state = _build_pause_snapshot_state(
                    task_id,
                    {
                        "projectId": task.project_id,
                        "branchId": task.branch_id,
                        "spaceId": task.space_id,
                        "agentRunId": run.id,
                        "pendingWrites": pending_write_refs,
                        "pendingActions": request.get("pendingActions") if isinstance(request.get("pendingActions"), list) else [],
                        "currentResponseState": "completed",
                        "currentContextState": pruning_result.get("retainedItems") if isinstance(pruning_result, dict) else current_context,
                        "rootMountPreview": root_mount,
                        "resumeMessage": pause_resume_message,
                        "taskObjective": task.current_objective or task.goal,
                        "takeoverProtocol": request.get("takeoverProtocol"),
                        "memoryRetrievalState": request.get("memoryRetrievalState"),
                        "memoryTagWrites": request.get("memoryTagWrites"),
                        "runtimeMetrics": request.get("runtimeMetrics"),
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
                paused_locator = f"agent-runtime/tasks/{task.id}/pause/{pause_snapshot['id']}"
                _cache_package_entry(
                    coordinator,
                    paused_locator,
                    {
                        "snapshotId": pause_snapshot["id"],
                        "flushedWrites": pause_state["flushedWrites"],
                        "pendingExternalActions": pause_snapshot_summary.pending_actions,
                        "resumeToken": pause_snapshot["resumeToken"],
                    },
                )
                paused_event = _persist_runtime_event(
                    session,
                    project_id=task.project_id,
                    aggregate_type="task",
                    aggregate_id=task.id,
                    event_type="task.paused",
                    locator=paused_locator,
                )
                runtime_timings["pauseTransitionMs"] = _elapsed_ms(pause_transition_started_at)
                runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
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
                    "takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
                    "takeoverProtocolRef": takeover_protocol_ref.model_dump(mode="json") if takeover_protocol_ref is not None else None,
                    "outboxRecords": {
                        "modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
                        "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                        "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                        "snapshotCreated": snapshot_created_event.model_dump(by_alias=True, mode="json"),
                        "writeCreated": write_event.model_dump(by_alias=True, mode="json"),
                        "taskPaused": paused_event.model_dump(by_alias=True, mode="json"),
                    },
                    "resume": resume_event_payload,
                    "memoryTagWrites": memory_tag_write_result,
                    "writeValidation": write_validation,
                    "rehydration": rehydration_result,
                    "runtimeMetricsArtifact": runtime_metrics_artifact,
                    "runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
                }

            complete_transition_started_at = perf_counter()
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
            if takeover_protocol is not None and takeover_protocol.work_tree is not None:
                takeover_protocol = takeover_protocol.model_copy(
                    update={
                        "status": "completed",
                        "work_tree": takeover_protocol.work_tree.model_copy(update={"status": "completed"}),
                    }
                )
                takeover_protocol_ref = persist_task_takeover_protocol(takeover_protocol, task_id=task.id, run_id=run.id)
            runtime_timings["completeTransitionMs"] = _elapsed_ms(complete_transition_started_at)
            runtime_timings["totalMs"] = _elapsed_ms(work_started_at)
            return {
                "status": "completed",
                "task": task.model_dump(by_alias=True, mode="json"),
                "run": run.model_dump(by_alias=True, mode="json"),
                "routeDecision": route_decision.model_dump(by_alias=True, mode="json"),
                "rootMount": root_mount,
                "createdNode": created_node.model_dump(by_alias=True, mode="json"),
                "pruning": pruning_result,
                "pruningEvents": pruning_events,
                "takeoverProtocol": takeover_protocol.model_dump(by_alias=True, mode="json") if takeover_protocol is not None else None,
                "takeoverProtocolRef": takeover_protocol_ref.model_dump(mode="json") if takeover_protocol_ref is not None else None,
                "modelInvocation": llm_result["invocation"],
                "outboxRecords": {
                    "modelInvocationCompleted": model_invocation_event.model_dump(by_alias=True, mode="json"),
                    "runCreated": run_created_event.model_dump(by_alias=True, mode="json"),
                    "routeSelected": route_event.model_dump(by_alias=True, mode="json"),
                    "writeCreated": write_event.model_dump(by_alias=True, mode="json"),
                },
                "resume": resume_event_payload,
                "memoryTagWrites": memory_tag_write_result,
                "writeValidation": write_validation,
                "rehydration": rehydration_result,
                "runtimeMetricsArtifact": runtime_metrics_artifact,
                "runtimeTimings": {**runtime_timings, "llm": llm_result.get("timings")},
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
