from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Any, Iterable
from .persistence import PromptAssetRepository, RuntimeRepository, TaskRepository, get_persistence_runtime
from .persistence.orm import AgentRunORM, ModelInvocationORM
from .persistence.repositories import WorkspaceBootstrapRepository
from .support import (
    ensure_state_subdir,
    load_workspace_dotenv,
    new_id,
    normalize_excerpt,
    read_json,
    relative_workspace_path,
    resolve_state_dir,
    resolve_workspace_root,
    utc_now,
    write_json,
)
_ALLOWED_GRANULARITIES = {"all", "run", "window", "turn", "tool", "artifact", "source"}
_GRANULARITY_SECTIONS = {
    "run": {"task", "agentRun", "summary", "coverage", "sources"},
    "window": {"windows"},
    "turn": {"turns"},
    "tool": {"tools"},
    "artifact": {"artifacts"},
    "source": {"sources"},
}
def parse_llm_work_granularities(value: str | Iterable[str] | None) -> set[str]:
    if value is None:
        return {"all"}
    if isinstance(value, str):
        raw_items = value.split(",")
    else:
        raw_items = []
        for item in value:
            raw_items.extend(str(item).split(","))
    granularities = {item.strip().lower() for item in raw_items if str(item).strip()}
    if not granularities:
        return {"all"}
    invalid = sorted(granularities - _ALLOWED_GRANULARITIES)
    if invalid:
        raise ValueError(f"Unsupported granularity: {', '.join(invalid)}")
    if "all" in granularities:
        return {"all"}
    return granularities
def filter_llm_work_analysis_payload(
    payload: dict[str, Any],
    granularities: str | Iterable[str] | None = None,
) -> dict[str, Any]:
    requested = parse_llm_work_granularities(granularities)
    if requested == {"all"}:
        return dict(payload)

    filtered: dict[str, Any] = {
        "analysis": dict(payload.get("analysis") or {}),
        "selector": dict(payload.get("selector") or {}),
    }
    sections = {"summary", "coverage"}
    for item in requested:
        sections.update(_GRANULARITY_SECTIONS.get(item, set()))
    for section in (
        "task",
        "agentRun",
        "summary",
        "coverage",
        "windows",
        "turns",
        "tools",
        "artifacts",
        "sources",
    ):
        if section in sections and section in payload:
            filtered[section] = payload[section]
    return filtered
def analyze_llm_work_run(
    *,
    task_id: str | None = None,
    run_id: str | None = None,
    invocation_id: str | None = None,
    granularities: str | Iterable[str] | None = None,
    persist: bool = True,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    if not any((task_id, run_id, invocation_id)):
        raise ValueError("One of task_id, run_id, or invocation_id is required.")

    load_workspace_dotenv(workspace_root)
    resolved_workspace_root = resolve_workspace_root(workspace_root)
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        resolved_target = _resolve_analysis_target(
            session,
            task_id=task_id,
            run_id=run_id,
            invocation_id=invocation_id,
        )
        payload = _build_llm_work_analysis_payload(
            session,
            task_id=resolved_target["taskId"],
            run_id=resolved_target.get("runId"),
            invocation_id=resolved_target.get("invocationId"),
            workspace_root=resolved_workspace_root,
        )

    if persist:
        payload = _persist_llm_work_analysis_payload(payload, resolved_workspace_root)
    return filter_llm_work_analysis_payload(payload, granularities)
def load_persisted_llm_work_analysis(
    analysis_id: str,
    *,
    granularities: str | Iterable[str] | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    resolved_workspace_root = resolve_workspace_root(workspace_root)
    path = ensure_state_subdir("analysis/llm-work", resolved_workspace_root) / f"{analysis_id}.json"
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        raise KeyError(analysis_id)
    return filter_llm_work_analysis_payload(payload, granularities)
def get_latest_llm_work_analysis_ref(
    task_id: str,
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any] | None:
    resolved_workspace_root = resolve_workspace_root(workspace_root)
    latest_path = ensure_state_subdir("analysis/llm-work/latest-by-task", resolved_workspace_root) / f"{task_id}.json"
    payload = read_json(latest_path, None)
    return payload if isinstance(payload, dict) else None
def load_latest_task_llm_work_analysis(
    task_id: str,
    *,
    granularities: str | Iterable[str] | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    latest = get_latest_llm_work_analysis_ref(task_id, workspace_root=workspace_root)
    if latest is None:
        raise KeyError(task_id)
    analysis_ref = latest.get("analysisRef") if isinstance(latest.get("analysisRef"), dict) else {}
    locator = str(analysis_ref.get("locator") or "").strip()
    if not locator:
        raise KeyError(task_id)
    path = _resolve_artifact_path(locator, resolve_workspace_root(workspace_root))
    payload = read_json(path, None) if path is not None else None
    if not isinstance(payload, dict):
        raise KeyError(task_id)
    return filter_llm_work_analysis_payload(payload, granularities)
def render_llm_work_analysis_markdown(payload: dict[str, Any]) -> str:
    analysis = payload.get("analysis") if isinstance(payload.get("analysis"), dict) else {}
    task = payload.get("task") if isinstance(payload.get("task"), dict) else {}
    run = payload.get("agentRun") if isinstance(payload.get("agentRun"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), dict) else {}
    windows = [item for item in payload.get("windows") or [] if isinstance(item, dict)]
    turns = [item for item in payload.get("turns") or [] if isinstance(item, dict)]
    tools = [item for item in payload.get("tools") or [] if isinstance(item, dict)]
    artifacts = [item for item in payload.get("artifacts") or [] if isinstance(item, dict)]
    cache_summary = summary.get("cacheSummary") if isinstance(summary.get("cacheSummary"), dict) else {}
    work_tree_debug = summary.get("workTreeDebug") if isinstance(summary.get("workTreeDebug"), dict) else {}

    lines = [
        "# LLM 工作分析报告",
        "",
        f"- analysisId: {analysis.get('analysisId') or 'unknown'}",
        f"- generatedAt: {analysis.get('generatedAt') or 'unknown'}",
        f"- taskId: {task.get('id') or summary.get('taskId') or 'unknown'}",
        f"- runId: {run.get('id') or summary.get('runId') or 'none'}",
        f"- invocationScope: {summary.get('invocationCount') or 0}",
        "",
        "## 概览",
        "",
        f"- 任务标题：{task.get('title') or '未命名任务'}",
        f"- 任务目标：{task.get('goal') or '未提供'}",
        f"- 运行状态：{run.get('status') or 'no-run'}",
        f"- 窗口数：{summary.get('windowCount') or 0}",
        f"- 轮次数：{summary.get('turnCount') or 0}",
        f"- 工具执行数：{summary.get('toolExecutionCount') or 0}",
        f"- 输入 token：{summary.get('totalInputTokens') or 0}",
        f"- 输出 token：{summary.get('totalOutputTokens') or 0}",
        f"- 成本：{summary.get('totalCostUsed') or 0.0}",
        f"- cache hit input：{cache_summary.get('cacheHitInputTokens') or 0}",
        f"- cache write input：{cache_summary.get('cacheWriteInputTokens') or 0}",
        f"- non-cache input：{cache_summary.get('nonCacheInputTokens') or 0}",
        f"- fallback 调用数：{summary.get('fallbackInvocationCount') or 0}",
        f"- 失败调用数：{summary.get('failedInvocationCount') or 0}",
        f"- 节点切换数：{work_tree_debug.get('nodeSwitchCount') or 0}",
        f"- approval 停点数：{work_tree_debug.get('approvalStopCount') or 0}",
        f"- mixed outcome 窗口数：{work_tree_debug.get('mixedOutcomeWindowCount') or 0}",
        "",
        "## 覆盖率",
        "",
        f"- request 工件：{coverage.get('requestArtifactsAvailable') or 0}/{coverage.get('invocationCount') or 0}",
        f"- response 工件：{coverage.get('responseArtifactsAvailable') or 0}/{coverage.get('invocationCount') or 0}",
        f"- prompt 工件：{coverage.get('promptArtifactsAvailable') or 0}/{coverage.get('invocationCount') or 0}",
        f"- metrics 工件：{coverage.get('metricsArtifactsAvailable') or 0}/{coverage.get('invocationCount') or 0}",
        f"- detailed tool 记录：{coverage.get('detailedToolRecords') or 0}",
        f"- takeover 协议：{'yes' if coverage.get('hasTakeoverProtocol') else 'no'}",
        f"- work-context-stack：{'yes' if coverage.get('hasWorkContextStack') else 'no'}",
        "",
    ]

    if windows:
        lines.extend(["## 窗口视图", ""])
        for window in windows:
            lines.append(
                f"- W{window.get('windowIndex') or '?'} | invocation={window.get('invocationId') or 'unknown'} | "
                f"model={window.get('resolvedModel') or window.get('requestedModel') or 'unknown'} | "
                f"finish={window.get('finishReason') or 'unknown'} | tools={window.get('toolExecutionCount') or 0} | "
                f"focus={window.get('currentFocus') or window.get('currentObjective') or 'n/a'}"
            )
            assistant_summary = str(window.get("assistantTextSummary") or "").strip()
            if assistant_summary:
                lines.append(f"  - 输出摘要：{assistant_summary}")
            work_tree_node = str(window.get("workTreeCurrentNodeId") or "").strip()
            if work_tree_node:
                lines.append(f"  - workTreeCurrentNodeId：{work_tree_node}")
            retrieval = window.get("memoryRetrievalState") if isinstance(window.get("memoryRetrievalState"), dict) else {}
            if retrieval:
                lines.append(
                    f"  - retrieval：matched={retrieval.get('matchedNodeCount') or 0}, "
                    f"materialized={retrieval.get('materializedNodeCount') or 0}, "
                    f"fingerprint={retrieval.get('retrievalFingerprint') or 'n/a'}"
                )
            cache = window.get("cacheSummary") if isinstance(window.get("cacheSummary"), dict) else {}
            if cache:
                lines.append(
                    f"  - cache：hit={cache.get('cacheHitInputTokens') or 0}, "
                    f"write={cache.get('cacheWriteInputTokens') or 0}, "
                    f"non-cache={cache.get('nonCacheInputTokens') or 0}"
                )
            work_tree_debug_window = window.get("workTreeDebug") if isinstance(window.get("workTreeDebug"), dict) else {}
            if work_tree_debug_window:
                lines.append(
                    f"  - transition={window.get('transitionOutcome') or 'n/a'}, "
                    f"topFrame={work_tree_debug_window.get('topFrameId') or window.get('topFrameId') or 'n/a'}, "
                    f"prefix={work_tree_debug_window.get('topFramePrefixCacheKey') or window.get('topFramePrefixCacheKey') or 'n/a'}"
                )
        lines.append("")

    timeline = work_tree_debug.get("timeline") if isinstance(work_tree_debug.get("timeline"), list) else []
    if timeline:
        lines.extend(["## 工作树时间线", ""])
        for item in timeline:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- W{item.get('windowIndex') or '?'} | node={item.get('nodeId') or 'n/a'} | "
                f"transition={item.get('transitionOutcome') or 'n/a'} | "
                f"reason={item.get('continuationReason') or 'n/a'} | "
                f"prefix={item.get('topFramePrefixCacheKey') or 'n/a'}"
            )
        lines.append("")

    if turns:
        lines.extend(["## Turn 视图", ""])
        for turn in turns:
            lines.append(
                f"- W{turn.get('windowIndex') or '?'} R{turn.get('roundIndex') or '?'} | mode={turn.get('mode') or 'unknown'} | "
                f"finish={turn.get('finishReason') or 'unknown'} | toolCalls={turn.get('toolCallCount') or 0} | "
                f"toolFailures={turn.get('toolFailureCount') or 0}"
            )
            assistant_preview = str(turn.get("assistantTextPreview") or "").strip()
            if assistant_preview:
                lines.append(f"  - 摘要：{assistant_preview}")
        lines.append("")

    if tools:
        lines.extend(["## Tool 视图", ""])
        for tool in tools:
            lines.append(
                f"- W{tool.get('windowIndex') or '?'} | {tool.get('toolName') or 'unknown'} | "
                f"success={tool.get('success')} | durationMs={tool.get('durationMs') or 0} | "
                f"round={tool.get('roundIndex') or '?'}"
            )
            result_preview = str(tool.get("resultPreview") or "").strip()
            if result_preview:
                lines.append(f"  - 结果：{result_preview}")
        lines.append("")

    if artifacts:
        lines.extend(["## 工件清单", ""])
        for artifact in artifacts:
            lines.append(
                f"- {artifact.get('kind') or 'artifact'} | exists={artifact.get('exists')} | "
                f"locator={artifact.get('locator') or 'n/a'}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
def _resolve_analysis_target(
    session,
    *,
    task_id: str | None,
    run_id: str | None,
    invocation_id: str | None,
) -> dict[str, str | None]:
    resolved_task_id = str(task_id).strip() if task_id is not None else None
    resolved_run_id = str(run_id).strip() if run_id is not None else None
    resolved_invocation_id = str(invocation_id).strip() if invocation_id is not None else None

    if resolved_invocation_id:
        invocation_model = session.get(ModelInvocationORM, resolved_invocation_id)
        if invocation_model is None:
            raise KeyError(resolved_invocation_id)
        if invocation_model.task_id is not None:
            if resolved_task_id is not None and resolved_task_id != invocation_model.task_id:
                raise ValueError("invocation_id does not belong to task_id.")
            resolved_task_id = str(invocation_model.task_id)
        if invocation_model.agent_run_id is not None:
            if resolved_run_id is not None and resolved_run_id != invocation_model.agent_run_id:
                raise ValueError("invocation_id does not belong to run_id.")
            resolved_run_id = str(invocation_model.agent_run_id)

    if resolved_run_id:
        run_model = session.get(AgentRunORM, resolved_run_id)
        if run_model is None:
            raise KeyError(resolved_run_id)
        if resolved_task_id is not None and resolved_task_id != run_model.task_id:
            raise ValueError("run_id does not belong to task_id.")
        resolved_task_id = str(run_model.task_id)

    if resolved_task_id is None:
        raise ValueError("Unable to resolve task_id from provided selector.")
    return {
        "taskId": resolved_task_id,
        "runId": resolved_run_id,
        "invocationId": resolved_invocation_id,
    }
def _build_llm_work_analysis_payload(
    session,
    *,
    task_id: str,
    run_id: str | None,
    invocation_id: str | None,
    workspace_root: Path,
) -> dict[str, Any]:
    task_repository = TaskRepository(session)
    runtime_repository = RuntimeRepository(session)
    prompt_repository = PromptAssetRepository(session)

    task_record = task_repository.get_task(task_id)
    if task_record is None:
        raise KeyError(task_id)

    task_payload = task_record.model_dump(by_alias=True, mode="json")
    run_records = task_repository.list_agent_runs(task_id, limit=500)
    run_payloads = [run.model_dump(by_alias=True, mode="json") for run in run_records]
    target_run = next((run for run in run_payloads if run.get("id") == run_id), None)
    if run_id is not None and target_run is None:
        raise KeyError(run_id)
    if target_run is None and run_payloads:
        target_run = run_payloads[0]

    invocation_records = runtime_repository.list_model_invocations(task_id=task_id, limit=2000)
    invocation_payloads = [record.model_dump(by_alias=True, mode="json") for record in invocation_records]
    if target_run is not None:
        run_invocations = [item for item in invocation_payloads if item.get("agentRunId") == target_run.get("id")]
    else:
        run_invocations = invocation_payloads
    if invocation_id is not None:
        run_invocations = [item for item in run_invocations if item.get("id") == invocation_id]
        if not run_invocations:
            raise KeyError(invocation_id)
    run_invocations.sort(key=lambda item: (str(item.get("createdAt") or ""), str(item.get("id") or "")))

    prompt_records = prompt_repository.list_prompt_compile_artifacts(task_id=task_id, app_id=task_payload.get("appId"), limit=500)
    prompt_payloads = [record.model_dump(by_alias=True, mode="json") for record in prompt_records]
    prompt_by_id = {item.get("id"): item for item in prompt_payloads if item.get("id")}
    prompt_by_invocation_id = {
        item.get("modelInvocationId"): item
        for item in prompt_payloads
        if item.get("modelInvocationId")
    }

    snapshot_records = task_repository.list_snapshots(task_id)
    snapshot_payloads = [record.model_dump(by_alias=True, mode="json") for record in snapshot_records]
    if target_run is not None:
        snapshot_payloads = [item for item in snapshot_payloads if item.get("agentRunId") == target_run.get("id")]

    route_decision_payloads = [
        record.model_dump(by_alias=True, mode="json")
        for record in runtime_repository.list_model_route_decisions(task_id=task_id, limit=500)
    ]
    if target_run is not None:
        route_decision_payloads = [
            item
            for item in route_decision_payloads
            if item.get("agentRunId") in {None, target_run.get("id")}
        ]

    mailbox_messages = [
        record.model_dump(by_alias=True, mode="json")
        for record in runtime_repository.list_mailbox_messages(task_id=task_id, limit=500)
    ]
    side_channel_events = [
        record.model_dump(by_alias=True, mode="json")
        for record in runtime_repository.list_side_channel_events(task_id=task_id, limit=500)
    ]
    if target_run is not None:
        side_channel_events = [
            item
            for item in side_channel_events
            if item.get("agentRunId") in {None, target_run.get("id")}
        ]
    mailbox_state = runtime_repository.get_mailbox_state(task_id)

    run_state = _load_run_state_payloads(task_id, target_run.get("id") if target_run is not None else None, workspace_root)
    windows: list[dict[str, Any]] = []
    turns: list[dict[str, Any]] = []
    tools: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    detailed_tool_records = 0

    for fallback_window_index, invocation in enumerate(run_invocations, start=1):
        prompt_artifact = prompt_by_invocation_id.get(invocation.get("id"))
        if prompt_artifact is None and invocation.get("promptCompileArtifactId"):
            prompt_artifact = prompt_by_id.get(invocation.get("promptCompileArtifactId"))

        invocation_artifacts = _load_invocation_artifacts(
            invocation,
            prompt_artifact=prompt_artifact,
            workspace_root=workspace_root,
        )
        artifacts.extend(invocation_artifacts["artifactRecords"])

        response_payload = invocation_artifacts.get("responsePayload") if isinstance(invocation_artifacts.get("responsePayload"), dict) else {}
        request_payload = invocation_artifacts.get("requestPayload") if isinstance(invocation_artifacts.get("requestPayload"), dict) else {}
        metrics_payload = invocation_artifacts.get("metricsPayload") if isinstance(invocation_artifacts.get("metricsPayload"), dict) else {}
        invocation_window_execution = invocation_artifacts.get("windowExecutionPayload") if isinstance(invocation_artifacts.get("windowExecutionPayload"), dict) else None
        window_execution = invocation_window_execution or _match_window_execution_record(
            run_state.get("windowExecutionArtifact") if isinstance(run_state.get("windowExecutionArtifact"), dict) else None,
            invocation_id=str(invocation.get("id") or ""),
            fallback_window_index=fallback_window_index,
            total_invocations=len(run_invocations),
        )
        window_index = _infer_window_index(
            invocation=invocation,
            request_payload=request_payload,
            response_payload=response_payload,
            metrics_payload=metrics_payload,
            window_execution=window_execution,
            fallback_window_index=fallback_window_index,
        )
        turn_records = _build_turn_records(invocation, request_payload, response_payload, window_index)
        tool_records = _build_tool_records(invocation, request_payload, response_payload, window_index)
        turns.extend(turn_records)
        tools.extend(tool_records)
        detailed_tool_records += len([item for item in tool_records if item.get("detailLevel") == "detailed"])
        windows.append(
            _build_window_record(
                invocation=invocation,
                prompt_artifact=prompt_artifact,
                request_payload=request_payload,
                response_payload=response_payload,
                metrics_payload=metrics_payload,
                window_execution=window_execution,
                window_index=window_index,
                tool_records=tool_records,
                turn_records=turn_records,
            )
        )

    artifacts.extend(run_state.get("artifactRecords") or [])
    windows.sort(key=lambda item: (int(item.get("windowIndex") or 0), str(item.get("invocationId") or "")))
    turns.sort(key=lambda item: (int(item.get("windowIndex") or 0), int(item.get("roundIndex") or 0), str(item.get("invocationId") or "")))
    tools.sort(key=lambda item: (int(item.get("windowIndex") or 0), int(item.get("roundIndex") or 0), str(item.get("toolExecutionId") or "")))

    summary = _build_summary(
        task_payload=task_payload,
        run_payload=target_run,
        windows=windows,
        turns=turns,
        tools=tools,
        invocations=run_invocations,
        snapshots=snapshot_payloads,
        mailbox_messages=mailbox_messages,
        side_channel_events=side_channel_events,
    )
    coverage = _build_coverage(
        invocations=run_invocations,
        windows=windows,
        turn_count=len(turns),
        tool_count=len(tools),
        detailed_tool_records=detailed_tool_records,
        artifacts=artifacts,
        run_state=run_state,
    )
    analysis_id = new_id(
        "llmwork",
        task_id,
        target_run.get("id") if target_run is not None else None,
        invocation_id,
        utc_now().isoformat(),
    )
    payload = {
        "analysis": {
            "analysisId": analysis_id,
            "kind": "llm-work-analysis",
            "version": "v0.1",
            "generatedAt": utc_now().isoformat(),
            "mode": "run-first-db-plus-state-artifacts",
            "analysisRef": None,
            "markdownRef": None,
        },
        "selector": {
            "taskId": task_id,
            "runId": target_run.get("id") if target_run is not None else None,
            "invocationId": invocation_id,
        },
        "task": task_payload,
        "agentRun": target_run,
        "summary": summary,
        "coverage": coverage,
        "windows": windows,
        "turns": turns,
        "tools": tools,
        "artifacts": artifacts,
        "sources": {
            "routeDecisions": route_decision_payloads,
            "snapshots": snapshot_payloads,
            "mailboxState": mailbox_state,
            "mailboxMessages": [
                {
                    "id": item.get("id"),
                    "messageKind": item.get("messageKind"),
                    "status": item.get("status"),
                    "workTreeNodeId": item.get("workTreeNodeId"),
                    "createdAt": item.get("createdAt"),
                }
                for item in mailbox_messages
            ],
            "sideChannelEvents": [
                {
                    "id": item.get("id"),
                    "eventKind": item.get("eventKind"),
                    "level": item.get("level"),
                    "summary": item.get("summary"),
                    "workTreeNodeId": item.get("workTreeNodeId"),
                    "createdAt": item.get("createdAt"),
                }
                for item in side_channel_events
            ],
            "takeoverProtocol": run_state.get("takeoverProtocol"),
            "workContextStack": run_state.get("workContextStack"),
            "windowExecutionArtifact": run_state.get("windowExecutionArtifact"),
        },
    }
    return payload
def _build_summary(
    *,
    task_payload: dict[str, Any],
    run_payload: dict[str, Any] | None,
    windows: list[dict[str, Any]],
    turns: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    invocations: list[dict[str, Any]],
    snapshots: list[dict[str, Any]],
    mailbox_messages: list[dict[str, Any]],
    side_channel_events: list[dict[str, Any]],
) -> dict[str, Any]:
    pending_mailbox_count = len([item for item in mailbox_messages if item.get("status") == "pending"])
    warning_events = len([item for item in side_channel_events if item.get("level") == "warning"])
    error_events = len([item for item in side_channel_events if item.get("level") == "error"])
    restorable_snapshots = len([item for item in snapshots if item.get("status") == "restorable"])
    fallback_invocations = len([item for item in invocations if item.get("status") == "fallback"])
    failed_invocations = len([item for item in invocations if item.get("status") == "failed"])
    restart_count = max(
        [int(item.get("restartCount") or 0) for item in windows] + [int((run_payload or {}).get("restartCount") or 0)],
        default=0,
    )
    latest_window_index = max([int(item.get("windowIndex") or 0) for item in windows], default=0)
    cache_summary = _build_analysis_cache_summary(windows)
    work_tree_debug = _build_analysis_work_tree_debug_summary(windows)
    return {
        "taskId": task_payload.get("id"),
        "runId": run_payload.get("id") if isinstance(run_payload, dict) else None,
        "invocationCount": len(invocations),
        "windowCount": len(windows),
        "turnCount": len(turns),
        "toolExecutionCount": len(tools),
        "restartCount": restart_count,
        "latestWindowIndex": latest_window_index,
        "totalInputTokens": sum(int(item.get("inputTokensUsed") or 0) for item in invocations),
        "totalOutputTokens": sum(int(item.get("outputTokensUsed") or 0) for item in invocations),
        "totalCostUsed": round(sum(float(item.get("costUsed") or 0.0) for item in invocations), 6),
        "fallbackInvocationCount": fallback_invocations,
        "failedInvocationCount": failed_invocations,
        "restorableSnapshotCount": restorable_snapshots,
        "mailboxMessageCount": len(mailbox_messages),
        "pendingMailboxCount": pending_mailbox_count,
        "warningEventCount": warning_events,
        "errorEventCount": error_events,
        "cacheHitInputTokens": cache_summary["cacheHitInputTokens"],
        "cacheWriteInputTokens": cache_summary["cacheWriteInputTokens"],
        "nonCacheInputTokens": cache_summary["nonCacheInputTokens"],
        "cacheSummary": cache_summary,
        "workTreeDebug": work_tree_debug,
    }
def _build_coverage(
    *,
    invocations: list[dict[str, Any]],
    windows: list[dict[str, Any]],
    turn_count: int,
    tool_count: int,
    detailed_tool_records: int,
    artifacts: list[dict[str, Any]],
    run_state: dict[str, Any],
) -> dict[str, Any]:
    def _artifact_count(kind: str) -> int:
        return len([item for item in artifacts if item.get("kind") == kind and item.get("exists")])

    return {
        "invocationCount": len(invocations),
        "windowCount": len(windows),
        "turnCount": turn_count,
        "toolCount": tool_count,
        "requestArtifactsAvailable": _artifact_count("llm-request"),
        "responseArtifactsAvailable": _artifact_count("llm-response"),
        "promptArtifactsAvailable": _artifact_count("compiled-prompt"),
        "metricsArtifactsAvailable": _artifact_count("runtime-metrics"),
        "windowExecutionArtifactsAvailable": _artifact_count("window-execution"),
        "detailedToolRecords": detailed_tool_records,
        "hasTakeoverProtocol": bool(run_state.get("takeoverProtocol")),
        "hasWorkContextStack": bool(run_state.get("workContextStack")),
    }
def _load_run_state_payloads(task_id: str, run_id: str | None, workspace_root: Path) -> dict[str, Any]:
    artifact_records: list[dict[str, Any]] = []
    if not run_id:
        return {
            "takeoverProtocol": None,
            "workContextStack": None,
            "windowExecutionArtifact": None,
            "artifactRecords": artifact_records,
        }

    state_dir = resolve_state_dir(workspace_root)
    takeover_path = state_dir / "runtime" / "takeover" / f"{task_id}-{run_id}.json"
    work_context_path = state_dir / "runtime" / "work-context-stack" / f"{task_id}-{run_id}.json"
    window_execution_path = state_dir / "runtime" / "window-executions" / f"{task_id}-{run_id}.json"

    takeover_payload = read_json(takeover_path, None)
    artifact_records.append(_artifact_record("takeover-protocol", takeover_path, workspace_root, task_id=task_id, run_id=run_id))
    work_context_payload = read_json(work_context_path, None)
    artifact_records.append(_artifact_record("work-context-stack", work_context_path, workspace_root, task_id=task_id, run_id=run_id))
    window_execution_payload = read_json(window_execution_path, None)
    artifact_records.append(_artifact_record("window-execution", window_execution_path, workspace_root, task_id=task_id, run_id=run_id))

    return {
        "takeoverProtocol": takeover_payload if isinstance(takeover_payload, dict) else None,
        "workContextStack": work_context_payload if isinstance(work_context_payload, dict) else None,
        "windowExecutionArtifact": window_execution_payload if isinstance(window_execution_payload, dict) else None,
        "artifactRecords": artifact_records,
    }
def _load_invocation_artifacts(
    invocation: dict[str, Any],
    *,
    prompt_artifact: dict[str, Any] | None,
    workspace_root: Path,
) -> dict[str, Any]:
    state_dir = resolve_state_dir(workspace_root)
    invocation_id = str(invocation.get("id") or "").strip()
    task_id = str(invocation.get("taskId") or "").strip() or None
    run_id = str(invocation.get("agentRunId") or "").strip() or None

    request_path = _resolve_artifact_path_from_ref(
        invocation.get("requestRef"),
        workspace_root,
        fallback=state_dir / "llm" / "requests" / f"{invocation_id}.json",
    )
    response_path = _resolve_artifact_path_from_ref(
        invocation.get("responseRef"),
        workspace_root,
        fallback=state_dir / "llm" / "responses" / f"{invocation_id}.json",
    )
    prompt_path = _resolve_artifact_path_from_ref(
        prompt_artifact.get("compiledMessagesRef") if isinstance(prompt_artifact, dict) else None,
        workspace_root,
        fallback=state_dir / "prompt" / "compiled" / f"{invocation_id}.json",
    )
    metrics_path = state_dir / "runtime" / "metrics" / f"{invocation_id}.json"
    window_execution_path = state_dir / "runtime" / "window-executions" / "by-invocation" / f"{invocation_id}.json"

    artifact_records = [
        _artifact_record("llm-request", request_path, workspace_root, task_id=task_id, run_id=run_id, invocation_id=invocation_id),
        _artifact_record("llm-response", response_path, workspace_root, task_id=task_id, run_id=run_id, invocation_id=invocation_id),
        _artifact_record("compiled-prompt", prompt_path, workspace_root, task_id=task_id, run_id=run_id, invocation_id=invocation_id),
        _artifact_record("runtime-metrics", metrics_path, workspace_root, task_id=task_id, run_id=run_id, invocation_id=invocation_id),
    ]
    return {
        "requestPayload": read_json(request_path, None) if request_path is not None else None,
        "responsePayload": read_json(response_path, None) if response_path is not None else None,
        "promptPayload": read_json(prompt_path, None) if prompt_path is not None else None,
        "metricsPayload": read_json(metrics_path, None),
        "windowExecutionPayload": read_json(window_execution_path, None),
        "artifactRecords": artifact_records,
    }
def _build_analysis_cache_summary(windows: list[dict[str, Any]]) -> dict[str, Any]:
    cache_hit_input_tokens = 0
    cache_write_input_tokens = 0
    non_cache_input_tokens = 0
    tracked_input_tokens = 0
    cache_hit_window_count = 0
    cache_write_window_count = 0
    for window in windows:
        cache = window.get("cacheSummary") if isinstance(window.get("cacheSummary"), dict) else {}
        cache_hit = max(_coerce_int(cache.get("cacheHitInputTokens")) or 0, 0)
        cache_write = max(_coerce_int(cache.get("cacheWriteInputTokens")) or 0, 0)
        non_cache = max(_coerce_int(cache.get("nonCacheInputTokens")) or 0, 0)
        tracked = max(_coerce_int(cache.get("trackedInputTokens")) or 0, cache_hit + cache_write + non_cache)
        cache_hit_input_tokens += cache_hit
        cache_write_input_tokens += cache_write
        non_cache_input_tokens += non_cache
        tracked_input_tokens += tracked
        if cache_hit > 0:
            cache_hit_window_count += 1
        if cache_write > 0:
            cache_write_window_count += 1
    denominator = tracked_input_tokens if tracked_input_tokens > 0 else 1
    return {
        "cacheHitInputTokens": cache_hit_input_tokens,
        "cacheWriteInputTokens": cache_write_input_tokens,
        "nonCacheInputTokens": non_cache_input_tokens,
        "trackedInputTokens": tracked_input_tokens,
        "cacheHitWindowCount": cache_hit_window_count,
        "cacheWriteWindowCount": cache_write_window_count,
        "cacheHitRatio0_1": round(cache_hit_input_tokens / denominator, 4) if tracked_input_tokens > 0 else 0.0,
        "cacheWriteRatio0_1": round(cache_write_input_tokens / denominator, 4) if tracked_input_tokens > 0 else 0.0,
    }
def _build_analysis_work_tree_debug_summary(windows: list[dict[str, Any]]) -> dict[str, Any]:
    timeline: list[dict[str, Any]] = []
    distinct_node_ids: list[str] = []
    distinct_prefix_cache_keys: list[str] = []
    continuation_reasons: list[str] = []
    node_switch_count = 0
    frame_switch_count = 0
    prefix_cache_change_count = 0
    approval_stop_count = 0
    child_bubble_count = 0
    mixed_outcome_window_count = 0
    previous_node_id: str | None = None
    previous_top_frame_id: str | None = None
    previous_prefix_cache_key: str | None = None
    for index, window in enumerate(windows, start=1):
        debug = window.get("workTreeDebug") if isinstance(window.get("workTreeDebug"), dict) else {}
        node_id = str(window.get("workTreeCurrentNodeId") or debug.get("topFrameNodeId") or "").strip() or None
        top_frame_id = str(window.get("topFrameId") or debug.get("topFrameId") or "").strip() or None
        prefix_cache_key = str(window.get("topFramePrefixCacheKey") or debug.get("topFramePrefixCacheKey") or "").strip() or None
        continuation_reason = str(debug.get("continuationReason") or window.get("resumePath") or window.get("restartTrigger") or "").strip() or None
        if node_id is not None and node_id not in distinct_node_ids:
            distinct_node_ids.append(node_id)
        if prefix_cache_key is not None and prefix_cache_key not in distinct_prefix_cache_keys:
            distinct_prefix_cache_keys.append(prefix_cache_key)
        if continuation_reason is not None and continuation_reason not in continuation_reasons:
            continuation_reasons.append(continuation_reason)
        node_changed = 1 if previous_node_id != node_id else 0
        frame_changed = 1 if previous_top_frame_id != top_frame_id else 0
        prefix_changed = 1 if previous_prefix_cache_key != prefix_cache_key else 0
        if index > 1:
            node_switch_count += node_changed
            frame_switch_count += frame_changed
            prefix_cache_change_count += prefix_changed
        approval_stop = max(_coerce_int(debug.get("approvalStop0_1")) or 0, 0)
        child_bubble = max(_coerce_int(debug.get("childBubble0_1")) or 0, 0)
        mixed_outcome = max(_coerce_int(debug.get("mixedOutcome0_1")) or 0, 0)
        approval_stop_count += approval_stop
        child_bubble_count += child_bubble
        mixed_outcome_window_count += mixed_outcome
        timeline.append(
            {
                "step": index,
                "windowIndex": window.get("windowIndex"),
                "invocationId": window.get("invocationId"),
                "nodeId": node_id,
                "topFrameId": top_frame_id,
                "topFramePrefixCacheKey": prefix_cache_key,
                "transitionOutcome": window.get("transitionOutcome"),
                "continuationReason": continuation_reason,
                "reworkReason": debug.get("reworkReason"),
                "nodeChanged0_1": node_changed,
                "frameChanged0_1": frame_changed,
                "prefixCacheChanged0_1": prefix_changed,
                "approvalStop0_1": approval_stop,
                "childBubble0_1": child_bubble,
                "mixedOutcome0_1": mixed_outcome,
            }
        )
        previous_node_id = node_id
        previous_top_frame_id = top_frame_id
        previous_prefix_cache_key = prefix_cache_key
    return {
        "distinctNodeIds": distinct_node_ids,
        "distinctNodeCount": len(distinct_node_ids),
        "distinctPrefixCacheKeys": distinct_prefix_cache_keys,
        "distinctPrefixCacheKeyCount": len(distinct_prefix_cache_keys),
        "continuationReasons": continuation_reasons,
        "nodeSwitchCount": node_switch_count,
        "frameSwitchCount": frame_switch_count,
        "prefixCacheChangeCount": prefix_cache_change_count,
        "approvalStopCount": approval_stop_count,
        "childBubbleCount": child_bubble_count,
        "mixedOutcomeWindowCount": mixed_outcome_window_count,
        "latestNodeId": distinct_node_ids[-1] if distinct_node_ids else None,
        "latestPrefixCacheKey": distinct_prefix_cache_keys[-1] if distinct_prefix_cache_keys else None,
        "timeline": timeline,
    }
def _build_window_record(
    *,
    invocation: dict[str, Any],
    prompt_artifact: dict[str, Any] | None,
    request_payload: dict[str, Any],
    response_payload: dict[str, Any],
    metrics_payload: dict[str, Any],
    window_execution: dict[str, Any] | None,
    window_index: int,
    tool_records: list[dict[str, Any]],
    turn_records: list[dict[str, Any]],
) -> dict[str, Any]:
    prompt_work_tree = prompt_artifact.get("workTreeSnapshot") if isinstance(prompt_artifact, dict) else {}
    if not isinstance(prompt_work_tree, dict):
        prompt_work_tree = {}
    runtime_metrics = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
    metrics_snapshot = metrics_payload.get("snapshot") if isinstance(metrics_payload.get("snapshot"), dict) else {}
    memory_state = window_execution.get("memoryRetrievalState") if isinstance(window_execution, dict) and isinstance(window_execution.get("memoryRetrievalState"), dict) else {}
    cache_summary = window_execution.get("cacheSummary") if isinstance(window_execution, dict) and isinstance(window_execution.get("cacheSummary"), dict) else {}
    if not cache_summary:
        usage = response_payload.get("usage") if isinstance(response_payload.get("usage"), dict) else {}
        input_tokens = max(_coerce_int(usage.get("inputTokens")) or 0, 0)
        cache_hit = max(_coerce_int(usage.get("cacheHitInputTokens")) or 0, 0)
        cache_write = max(_coerce_int(usage.get("cacheWriteInputTokens")) or 0, 0)
        non_cache = max(_coerce_int(usage.get("nonCacheInputTokens")) or max(input_tokens - cache_hit, 0), 0)
        tracked = max(input_tokens, cache_hit + cache_write + non_cache)
        denominator = tracked if tracked > 0 else 1
        cache_summary = {
            "inputTokens": input_tokens,
            "cacheHitInputTokens": cache_hit,
            "cacheWriteInputTokens": cache_write,
            "nonCacheInputTokens": non_cache,
            "trackedInputTokens": tracked,
            "cacheHitRatio0_1": round(cache_hit / denominator, 4) if tracked > 0 else 0.0,
            "cacheWriteRatio0_1": round(cache_write / denominator, 4) if tracked > 0 else 0.0,
        }
    work_tree_debug = window_execution.get("workTreeDebug") if isinstance(window_execution, dict) and isinstance(window_execution.get("workTreeDebug"), dict) else {}
    top_frame_id = (window_execution or {}).get("topFrameId") or work_tree_debug.get("topFrameId")
    top_frame_prefix_cache_key = (window_execution or {}).get("topFramePrefixCacheKey") or work_tree_debug.get("topFramePrefixCacheKey")
    assistant_text = str(response_payload.get("assistantText") or invocation.get("assistantTextSummary") or "").strip()
    return {
        "windowIndex": window_index,
        "invocationId": invocation.get("id"),
        "status": invocation.get("status"),
        "requestedModel": invocation.get("requestedModel"),
        "requestedProvider": invocation.get("requestedProvider"),
        "resolvedModel": invocation.get("resolvedModel"),
        "resolvedProvider": invocation.get("resolvedProvider"),
        "promptCompileArtifactId": invocation.get("promptCompileArtifactId"),
        "createdAt": invocation.get("createdAt"),
        "finishReason": response_payload.get("finishReason") or (window_execution or {}).get("llm", {}).get("finishReason"),
        "assistantTextSummary": normalize_excerpt(assistant_text, 240) if assistant_text else invocation.get("assistantTextSummary"),
        "currentObjective": (window_execution or {}).get("currentObjective"),
        "currentFocus": (window_execution or {}).get("currentFocus"),
        "sourceSnapshotId": (window_execution or {}).get("sourceSnapshotId"),
        "targetSnapshotId": (window_execution or {}).get("targetSnapshotId"),
        "restartTrigger": (window_execution or {}).get("restartTrigger"),
        "resumePath": (window_execution or {}).get("resumePath"),
        "transitionStage": (window_execution or {}).get("transitionStage"),
        "transitionOutcome": (window_execution or {}).get("transitionOutcome"),
        "workTreeCurrentNodeId": (window_execution or {}).get("workTreeCurrentNodeId") or prompt_work_tree.get("currentNodeId"),
        "workTreeStatus": (window_execution or {}).get("workTreeStatus") or prompt_work_tree.get("status"),
        "workTreeRecoveryAnchor": (window_execution or {}).get("workTreeRecoveryAnchor") or prompt_work_tree.get("recoveryAnchor"),
        "topFrameId": top_frame_id,
        "topFramePrefixCacheKey": top_frame_prefix_cache_key,
        "memoryRetrievalState": memory_state or None,
        "cacheSummary": cache_summary,
        "runtimeMetrics": {
            "windowIndex": runtime_metrics.get("windowIndex") or metrics_snapshot.get("windowIndex") or window_index,
            "restartCount": runtime_metrics.get("restartCount") or metrics_snapshot.get("restartCount") or invocation.get("restartCount") or 0,
            "effectiveContextWindow": runtime_metrics.get("effectiveContextWindow") or (window_execution or {}).get("effectiveContextWindow") or 0,
            "windowRestartThreshold": runtime_metrics.get("windowRestartThreshold") or (window_execution or {}).get("windowRestartThreshold") or 0,
            "windowSpanTokens": runtime_metrics.get("windowSpanTokens") or (window_execution or {}).get("windowSpanTokens") or 0,
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens") or metrics_snapshot.get("cumulativeWindowSpanTokens") or invocation.get("cumulativeWindowSpanTokens") or 0,
        },
        "toolExecutionCount": len(tool_records),
        "roundCount": len(turn_records),
        "planningStub0_1": (((window_execution or {}).get("llm") or {}).get("planningStub0_1") if isinstance((window_execution or {}).get("llm"), dict) else None),
        "workTreeDebug": work_tree_debug or None,
    }
