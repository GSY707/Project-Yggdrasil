from .llm_runtime_part_a import *  # noqa: F401,F403
from .llm_runtime_part_a import _elapsed_ms
def _normalize_conversation_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            for key in ("text", "input_text", "output_text", "content"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value)
                    break
        return "\n".join(parts)
    return ""
def _to_serialized_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    serialized: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")
        serialized.append(
            {
                "role": role,
                "content": _normalize_conversation_content(message.get("content")),
            }
        )
    return serialized
def _safe_load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None
def _runtime_metrics_for_response(task: Any, request: dict[str, Any]) -> dict[str, Any]:
    request_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    merged = dict(request_metrics)
    merged["windowIndex"] = max(int(merged.get("windowIndex") or 0), int(getattr(task, "window_index", 0) or 0))
    merged["restartCount"] = max(int(merged.get("restartCount") or 0), int(getattr(task, "restart_count", 0) or 0))
    merged["cumulativeWindowSpanTokens"] = max(
        int(merged.get("cumulativeWindowSpanTokens") or 0),
        int(getattr(task, "cumulative_window_span_tokens", 0) or 0),
    )
    merged["carryForwardLossCount"] = max(
        int(merged.get("carryForwardLossCount") or 0),
        int(getattr(task, "carry_forward_loss_count", 0) or 0),
    )
    return merged
def _upsert_task_conversation_record(
    *,
    workspace_root: Path,
    task_id: str,
    invocation_entry: dict[str, Any],
) -> None:
    now = utc_now().isoformat()

    state_dir = ensure_state_subdir("llm/task-conversations", workspace_root)
    state_record_path = state_dir / f"task_{task_id}.json"
    state_index_path = state_dir / "index.json"

    tmp_dir = workspace_root / "tmp" / "task-conversations" / "data"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_record_path = tmp_dir / f"task_{task_id}.json"
    tmp_index_path = tmp_dir / "index.json"

    for record_path, index_path in (
        (state_record_path, state_index_path),
        (tmp_record_path, tmp_index_path),
    ):
        record_payload = _safe_load_json(record_path) or {
            "taskId": task_id,
            "createdAt": now,
            "updatedAt": now,
            "invocations": [],
        }
        invocations = [
            item
            for item in (record_payload.get("invocations") or [])
            if isinstance(item, dict) and str(item.get("invocationId") or "") != str(invocation_entry.get("invocationId") or "")
        ]
        invocations.append(dict(invocation_entry))
        invocations.sort(
            key=lambda item: (
                int(item.get("windowIndex") or 0),
                str(item.get("endedAt") or ""),
                str(item.get("invocationId") or ""),
            )
        )
        record_payload["taskId"] = task_id
        record_payload["updatedAt"] = now
        record_payload["invocationCount"] = len(invocations)
        record_payload["invocations"] = invocations
        if invocations:
            latest = invocations[-1]
            record_payload["latestInvocationId"] = latest.get("invocationId")
            record_payload["latestWindowIndex"] = latest.get("windowIndex")
            record_payload["latestStatus"] = latest.get("status")
        write_json(record_path, record_payload)

        index_payload = _safe_load_json(index_path) or {"updatedAt": now, "tasks": []}
        tasks = [item for item in (index_payload.get("tasks") or []) if isinstance(item, dict)]
        task_items = [item for item in tasks if str(item.get("taskId") or "") != task_id]
        latest_entry = invocations[-1] if invocations else {}
        task_items.append(
            {
                "taskId": task_id,
                "recordPath": record_path.name,
                "invocationCount": len(invocations),
                "latestInvocationId": latest_entry.get("invocationId"),
                "latestWindowIndex": latest_entry.get("windowIndex"),
                "latestStatus": latest_entry.get("status"),
                "updatedAt": now,
            }
        )
        task_items.sort(key=lambda item: str(item.get("updatedAt") or ""), reverse=True)
        index_payload["updatedAt"] = now
        index_payload["tasks"] = task_items
        write_json(index_path, index_payload)
