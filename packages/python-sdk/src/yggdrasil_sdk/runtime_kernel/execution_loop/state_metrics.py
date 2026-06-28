import json
import logging
import re
from hashlib import sha1
from .._common import *  # noqa: F403,F401
from ..root_mount import *  # noqa: F403,F401
from ..snapshot import *  # noqa: F403,F401
from ..execution_control import *  # noqa: F403,F401
from ..takeover import *  # noqa: F403,F401
from ...contracts import RuntimeMetricsSnapshot
from ...llm_runtime import SafeShutdownInterrupt
from ..shutdown_control import is_shutdown_requested as _is_shutdown_requested
from ..snapshot import save_pending_tool_calls_snapshot
_logger = logging.getLogger(__name__)
_MEMORY_WRITE_TAG_PATTERN = re.compile(
    r"<memory-write(?P<attrs>[^>]*)>(?P<content>.*?)</memory-write>",
    re.IGNORECASE | re.DOTALL,
)
_WORK_TREE_ACTION_TAG_PATTERN = re.compile(
    r"<work-node-(?P<action>create|enter)(?P<attrs>[^>]*)>(?P<content>.*?)</work-node-(?P=action)>",
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


def _max_uncompressed_tail_before_decompress(request: dict[str, Any] | None) -> int:
    if not isinstance(request, dict):
        return 1
    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    return max(
        _int_metric(
            request.get("maxUncompressedTailBeforeDecompress"),
            _int_metric(request_metrics.get("maxUncompressedTailBeforeDecompress"), 1),
        ),
        0,
    )


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
    max_uncompressed_tail_before_decompress = _max_uncompressed_tail_before_decompress(request)

    window_index = max(
        _int_metric(request.get("windowIndex"), _int_metric(request_metrics.get("windowIndex"), getattr(task, "window_index", 1))),
        1,
    )
    restart_count = max(
        _int_metric(request.get("restartCount"), _int_metric(request_metrics.get("restartCount"), getattr(task, "restart_count", 0))),
        0,
    )
    cumulative_window_span_tokens = max(
        _int_metric(
            request.get("cumulativeWindowSpanTokens"),
            _int_metric(request_metrics.get("cumulativeWindowSpanTokens"), getattr(task, "cumulative_window_span_tokens", 0)),
        ),
        0,
    )
    # Use window-span semantics as a floor so cumulative span can reflect restart traversal,
    # not only the currently materialized context token count.
    if effective_context_window > 0:
        span_floor = effective_context_window * max(window_index - 1, restart_count)
        if span_floor > cumulative_window_span_tokens:
            cumulative_window_span_tokens = span_floor

    return {
        "windowIndex": window_index,
        "restartCount": restart_count,
        "compressionCount": max(_int_metric(request.get("compressionCount"), _int_metric(request_metrics.get("compressionCount"), 0)), 0),
        "cumulativeWindowSpanTokens": cumulative_window_span_tokens,
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
        "maxUncompressedTailBeforeDecompress": max_uncompressed_tail_before_decompress,
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
    input_tokens = max(_int_metric(usage.get("inputTokens"), 0), 0)
    cache_hit_input_tokens = max(_int_metric(usage.get("cacheHitInputTokens"), 0), 0)
    cache_write_input_tokens = max(_int_metric(usage.get("cacheWriteInputTokens"), 0), 0)
    non_cache_input_tokens = max(_int_metric(usage.get("nonCacheInputTokens"), max(input_tokens - cache_hit_input_tokens, 0)), 0)
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
        cacheHitInputTokens=cache_hit_input_tokens,
        cacheWriteInputTokens=cache_write_input_tokens,
        nonCacheInputTokens=non_cache_input_tokens,
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
    if bool(request.get("forceWindowRestart")) and effective_context:
        return "forceWindowRestart", window_span_tokens
    effective_context_window = _int_metric(runtime_metrics.get("effectiveContextWindow"), 0)
    restart_threshold = _int_metric(runtime_metrics.get("windowRestartThreshold"), 0)
    if effective_context_window > 0 and restart_threshold > 0 and window_span_tokens >= restart_threshold:
        if _int_metric(runtime_metrics.get("forcedWindowRestartBudget"), 0) > 0:
            return "forcedWindowRestartBudget", window_span_tokens
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
    return _runtime_pointer_fields(request).get("currentNodeId")
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

__all__ = [name for name in globals() if not name.startswith("__")]
