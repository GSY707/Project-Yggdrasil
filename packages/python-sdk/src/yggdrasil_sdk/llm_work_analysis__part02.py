def _build_turn_records(
    invocation: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    window_index: int,
) -> list[dict[str, Any]]:
    rounds = response_payload.get("rounds") if isinstance(response_payload.get("rounds"), list) else None
    if rounds is None:
        rounds = request_payload.get("rounds") if isinstance(request_payload.get("rounds"), list) else []
    records: list[dict[str, Any]] = []
    for fallback_index, summary in enumerate(rounds, start=1):
        if not isinstance(summary, dict):
            continue
        round_index = _coerce_int(summary.get("index")) or fallback_index
        tool_calls = summary.get("toolCalls") if isinstance(summary.get("toolCalls"), list) else []
        tool_failures = summary.get("toolFailures") if isinstance(summary.get("toolFailures"), list) else []
        records.append(
            {
                "turnId": f"{invocation.get('id')}:round:{round_index}",
                "invocationId": invocation.get("id"),
                "windowIndex": window_index,
                "roundIndex": round_index,
                "mode": summary.get("mode"),
                "finishReason": summary.get("finishReason"),
                "latencyMs": summary.get("latencyMs"),
                "firstTokenLatencyMs": summary.get("firstTokenLatencyMs"),
                "reasoningContentPresent": bool(summary.get("reasoningContentPresent")),
                "toolCallCount": len(tool_calls),
                "toolCalls": [str(item) for item in tool_calls],
                "toolFailureCount": len(tool_failures),
                "budgetCheckResult": summary.get("budgetCheckResult"),
                "budgetOverrunResult": summary.get("budgetOverrunResult"),
                "assistantTextPreview": normalize_excerpt(str(response_payload.get("assistantText") or ""), 240) if fallback_index == len(rounds) else None,
                "rawSummary": dict(summary),
            }
        )
    if records:
        return records
    assistant_preview = normalize_excerpt(str(response_payload.get("assistantText") or invocation.get("assistantTextSummary") or ""), 240)
    return [
        {
            "turnId": f"{invocation.get('id')}:round:1",
            "invocationId": invocation.get("id"),
            "windowIndex": window_index,
            "roundIndex": 1,
            "mode": response_payload.get("mode") or invocation.get("status"),
            "finishReason": response_payload.get("finishReason"),
            "latencyMs": invocation.get("latencyMs"),
            "firstTokenLatencyMs": response_payload.get("firstTokenLatencyMs"),
            "reasoningContentPresent": False,
            "toolCallCount": 0,
            "toolCalls": [],
            "toolFailureCount": 0,
            "budgetCheckResult": None,
            "budgetOverrunResult": None,
            "assistantTextPreview": assistant_preview,
            "rawSummary": None,
            "synthetic": True,
        }
    ]
def _build_tool_records(
    invocation: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    window_index: int,
) -> list[dict[str, Any]]:
    rounds = response_payload.get("rounds") if isinstance(response_payload.get("rounds"), list) else []
    round_indexes: list[int | None] = []
    for fallback_index, summary in enumerate(rounds, start=1):
        if not isinstance(summary, dict):
            continue
        round_index = _coerce_int(summary.get("index")) or fallback_index
        tool_calls = summary.get("toolCalls") if isinstance(summary.get("toolCalls"), list) else []
        round_indexes.extend([round_index] * len(tool_calls))

    tool_executions = response_payload.get("toolExecutions") if isinstance(response_payload.get("toolExecutions"), list) else None
    if tool_executions is None:
        tool_executions = request_payload.get("toolExecutions") if isinstance(request_payload.get("toolExecutions"), list) else []

    records: list[dict[str, Any]] = []
    for index, execution in enumerate(tool_executions, start=1):
        if not isinstance(execution, dict):
            continue
        tool = execution.get("tool") if isinstance(execution.get("tool"), dict) else {}
        result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
        round_index = round_indexes[index - 1] if index - 1 < len(round_indexes) else None
        failure = execution.get("failure") if isinstance(execution.get("failure"), dict) else {}
        records.append(
            {
                "toolExecutionId": f"{invocation.get('id')}:tool:{index}",
                "invocationId": invocation.get("id"),
                "windowIndex": window_index,
                "roundIndex": round_index,
                "toolName": tool.get("name"),
                "success": bool(execution.get("success")),
                "durationMs": execution.get("durationMs"),
                "toolCallId": execution.get("toolCallId"),
                "status": result.get("status") or ("ok" if execution.get("success") else "error"),
                "sourceWorkTreeNodeId": result.get("sourceWorkTreeNodeId") or failure.get("sourceWorkTreeNodeId"),
                "resultPreview": normalize_excerpt(str(result), 240),
                "failureSummary": failure.get("summary") or failure.get("message") or failure.get("kind"),
                "detailLevel": "detailed",
            }
        )
    if records:
        return records

    summaries = response_payload.get("toolExecutionSummaries") if isinstance(response_payload.get("toolExecutionSummaries"), list) else []
    for index, summary in enumerate(summaries, start=1):
        if not isinstance(summary, dict):
            continue
        records.append(
            {
                "toolExecutionId": f"{invocation.get('id')}:tool-summary:{index}",
                "invocationId": invocation.get("id"),
                "windowIndex": window_index,
                "roundIndex": None,
                "toolName": summary.get("tool"),
                "success": summary.get("success"),
                "durationMs": None,
                "toolCallId": None,
                "status": summary.get("status"),
                "sourceWorkTreeNodeId": None,
                "resultPreview": summary.get("resultPreview"),
                "failureSummary": None,
                "detailLevel": "summary",
            }
        )
    return records
def _infer_window_index(
    *,
    invocation: dict[str, Any],
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    metrics_payload: dict[str, Any],
    window_execution: dict[str, Any] | None,
    fallback_window_index: int,
) -> int:
    metrics_snapshot = metrics_payload.get("snapshot") if isinstance(metrics_payload.get("snapshot"), dict) else {}
    response_metrics = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
    request_metadata = request_payload.get("promptMetadata") if isinstance(request_payload.get("promptMetadata"), dict) else {}
    for candidate in (
        response_metrics.get("windowIndex"),
        metrics_snapshot.get("windowIndex"),
        (window_execution or {}).get("windowIndex"),
        request_metadata.get("windowIndex"),
        invocation.get("windowIndex"),
        fallback_window_index,
    ):
        normalized = _coerce_int(candidate)
        if normalized is not None and normalized > 0:
            return normalized
    return fallback_window_index
def _match_window_execution_record(
    window_execution: dict[str, Any] | None,
    *,
    invocation_id: str,
    fallback_window_index: int,
    total_invocations: int,
) -> dict[str, Any] | None:
    if not isinstance(window_execution, dict):
        return None
    if str(window_execution.get("invocationId") or "").strip() == invocation_id:
        return window_execution
    if total_invocations == 1:
        return window_execution
    if _coerce_int(window_execution.get("windowIndex")) == fallback_window_index:
        return window_execution
    return None
def _artifact_record(
    kind: str,
    path: Path | None,
    workspace_root: Path,
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    invocation_id: str | None = None,
) -> dict[str, Any]:
    exists = bool(path is not None and path.exists())
    return {
        "kind": kind,
        "taskId": task_id,
        "runId": run_id,
        "invocationId": invocation_id,
        "locator": relative_workspace_path(path, workspace_root) if path is not None else None,
        "path": path.as_posix() if path is not None else None,
        "exists": exists,
    }
def _resolve_artifact_path_from_ref(
    ref: dict[str, Any] | None,
    workspace_root: Path,
    *,
    fallback: Path,
) -> Path:
    if isinstance(ref, dict):
        locator = str(ref.get("locator") or "").strip()
        if locator:
            resolved = _resolve_artifact_path(locator, workspace_root)
            if resolved is not None:
                return resolved
    return fallback
def _resolve_artifact_path(locator: str | None, workspace_root: Path) -> Path | None:
    if not locator:
        return None
    candidate = Path(locator)
    if candidate.is_absolute():
        return candidate
    return (workspace_root / candidate).resolve()
def _persist_llm_work_analysis_payload(payload: dict[str, Any], workspace_root: Path) -> dict[str, Any]:
    analysis = dict(payload.get("analysis") or {})
    analysis_id = str(analysis.get("analysisId") or new_id("llmwork", utc_now().isoformat()))
    analysis_dir = ensure_state_subdir("analysis/llm-work", workspace_root)
    latest_dir = ensure_state_subdir("analysis/llm-work/latest-by-task", workspace_root)
    json_path = analysis_dir / f"{analysis_id}.json"
    markdown_path = analysis_dir / f"{analysis_id}.md"
    analysis["analysisRef"] = {"type": "file", "locator": relative_workspace_path(json_path, workspace_root)}
    analysis["markdownRef"] = {"type": "file", "locator": relative_workspace_path(markdown_path, workspace_root)}
    persisted = dict(payload)
    persisted["analysis"] = analysis
    write_json(json_path, persisted)
    markdown_path.write_text(render_llm_work_analysis_markdown(persisted), encoding="utf-8")

    selector = persisted.get("selector") if isinstance(persisted.get("selector"), dict) else {}
    task_id = str(selector.get("taskId") or "").strip()
    if task_id:
        latest_payload = {
            "taskId": task_id,
            "runId": selector.get("runId"),
            "invocationId": selector.get("invocationId"),
            "analysisId": analysis_id,
            "generatedAt": analysis.get("generatedAt"),
            "analysisRef": analysis.get("analysisRef"),
            "markdownRef": analysis.get("markdownRef"),
            "summary": persisted.get("summary"),
        }
        write_json(latest_dir / f"{task_id}.json", latest_payload)
    return persisted
def _coerce_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Analyze Project Yggdrasil LLM work traces.")
    parser.add_argument("--task-id", dest="task_id")
    parser.add_argument("--run-id", dest="run_id")
    parser.add_argument("--invocation-id", dest="invocation_id")
    parser.add_argument("--granularity", default="all")
    parser.add_argument("--workspace-root")
    parser.add_argument("--output")
    parser.add_argument("--format", choices=["json", "md"], default="json")
    parser.add_argument("--no-persist", action="store_true")
    args = parser.parse_args(argv)

    workspace_root = Path(args.workspace_root).resolve() if args.workspace_root else None
    payload = analyze_llm_work_run(
        task_id=args.task_id,
        run_id=args.run_id,
        invocation_id=args.invocation_id,
        granularities=args.granularity,
        persist=not args.no_persist,
        workspace_root=workspace_root,
    )
    output_text = (
        json.dumps(payload, ensure_ascii=False, indent=2)
        if args.format == "json"
        else render_llm_work_analysis_markdown(payload)
    )
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text, encoding="utf-8")
        return
    print(output_text)
if __name__ == "__main__":
    main()
__all__ = [
    "analyze_llm_work_run",
    "filter_llm_work_analysis_payload",
    "get_latest_llm_work_analysis_ref",
    "load_latest_task_llm_work_analysis",
    "load_persisted_llm_work_analysis",
    "main",
    "parse_llm_work_granularities",
    "render_llm_work_analysis_markdown",
]