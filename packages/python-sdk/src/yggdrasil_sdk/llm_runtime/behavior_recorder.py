from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from ..support import normalize_excerpt, read_json, utc_now, write_json

_WORK_DIRECTIVE_RE = re.compile(
    r"<(?P<tag>work-node-create|work-node-enter|work-node-complete|work-node-handoff|work-node-skip|work-node-prune)\b(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_WORK_NATURAL_LANGUAGE_CLAIM_RE = re.compile(
    r"("
    r"创建\s*(?:并\s*)?进入\s*(?:leaf|叶子节点|叶节点|子节点)"
    r"|进入\s*(?:leaf|叶子节点|叶节点|子节点)"
    r"|切换(?:到|至)?\s*(?:leaf|叶子节点|叶节点|子节点)"
    r"|转入\s*(?:leaf|叶子节点|叶节点|子节点)"
    r"|(?:leaf|叶节点|子节点)\s*(?:handoff|交接|移交)"
    r"|返回父节点|回到父节点|交给父节点"
    r"|create(?:d|s|ing)?(?:\s+and\s+enter(?:ed|ing)?)?\s+(?:a\s+)?(?:child|leaf)\b"
    r"|enter(?:ed|ing)?\s+(?:a\s+)?(?:child|leaf)\b"
    r"|switch(?:ed|ing)?\s+(?:to\s+)?(?:a\s+)?(?:child|leaf)\b"
    r"|leaf\s+handoff"
    r"|return(?:ed|ing)?\s+to\s+parent"
    r")",
    re.IGNORECASE | re.DOTALL,
)
_ATTR_RE = re.compile(r"(?P<name>[A-Za-z_:][-A-Za-z0-9_:.]*)=(?P<quote>[\"'])(?P<value>.*?)(?P=quote)")
_SELF_REPORTED_TOOL_COUNT_RE = re.compile(
    r"`?(?P<tool>[A-Za-z][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)+)`?\s*\((?P<count>\d+)\s*次",
    re.IGNORECASE,
)


def _value(source: Any, key: str, default: Any = None) -> Any:
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _path_locator(path: Path | None, workspace_root: Path) -> str | None:
    if path is None:
        return None
    resolved_path = path.resolve()
    root = workspace_root.resolve()
    try:
        return resolved_path.relative_to(root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _state_dir(workspace_root: Path) -> Path:
    configured = os.environ.get("YGGDRASIL_STATE_DIR")
    if configured:
        configured_path = Path(configured)
        return configured_path if configured_path.is_absolute() else workspace_root / configured_path
    configured_root = os.environ.get("YGGDRASIL_STATE_ROOT")
    if configured_root:
        root_path = Path(configured_root)
        root = root_path if root_path.is_absolute() else workspace_root / root_path
        return root / "state"
    return workspace_root / ".yggdrasil" / "state"


def _json_file(path: Path | None) -> dict[str, Any]:
    payload = read_json(path, None) if path is not None else None
    return payload if isinstance(payload, dict) else {}


def _tool_name(execution: dict[str, Any]) -> str:
    tool = execution.get("tool") if isinstance(execution.get("tool"), dict) else {}
    return str(tool.get("name") or execution.get("toolName") or "unknown").strip() or "unknown"


def _round_indexes(rounds: list[dict[str, Any]]) -> list[int | None]:
    indexes: list[int | None] = []
    for fallback_index, summary in enumerate(rounds, start=1):
        if not isinstance(summary, dict):
            continue
        raw_index = summary.get("index")
        try:
            round_index = int(raw_index)
        except Exception:
            round_index = fallback_index
        tool_calls = summary.get("toolCalls") if isinstance(summary.get("toolCalls"), list) else []
        indexes.extend([round_index] * len(tool_calls))
    return indexes


def _tool_records(response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    tool_executions = response_payload.get("toolExecutions")
    if not isinstance(tool_executions, list):
        return []
    rounds = response_payload.get("rounds") if isinstance(response_payload.get("rounds"), list) else []
    indexes = _round_indexes([item for item in rounds if isinstance(item, dict)])
    records: list[dict[str, Any]] = []
    for index, execution in enumerate(tool_executions, start=1):
        if not isinstance(execution, dict):
            continue
        result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
        failure = execution.get("failure") if isinstance(execution.get("failure"), dict) else {}
        records.append(
            {
                "index": index,
                "roundIndex": indexes[index - 1] if index - 1 < len(indexes) else None,
                "toolName": _tool_name(execution),
                "requestedName": execution.get("requestedName"),
                "toolCallId": execution.get("toolCallId"),
                "success": bool(execution.get("success")),
                "durationMs": execution.get("durationMs"),
                "status": result.get("status") or ("ok" if execution.get("success") else "error"),
                "resultPreview": normalize_excerpt(str(result), 320),
                "failureSummary": failure.get("summary") or failure.get("message") or failure.get("kind"),
            }
        )
    return records


def _round_tool_counts(rounds: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for summary in rounds:
        if not isinstance(summary, dict):
            continue
        for tool_name in summary.get("toolCalls") or []:
            text = str(tool_name or "").strip()
            if text:
                counts[text] += 1
    return counts


def _round_records(response_payload: dict[str, Any]) -> list[dict[str, Any]]:
    rounds = response_payload.get("rounds") if isinstance(response_payload.get("rounds"), list) else []
    records: list[dict[str, Any]] = []
    for fallback_index, summary in enumerate(rounds, start=1):
        if not isinstance(summary, dict):
            continue
        try:
            round_index = int(summary.get("index"))
        except Exception:
            round_index = fallback_index
        tool_calls = summary.get("toolCalls") if isinstance(summary.get("toolCalls"), list) else []
        tool_failures = summary.get("toolFailures") if isinstance(summary.get("toolFailures"), list) else []
        records.append(
            {
                "roundIndex": round_index,
                "mode": summary.get("mode"),
                "finishReason": summary.get("finishReason"),
                "latencyMs": summary.get("latencyMs"),
                "firstTokenLatencyMs": summary.get("firstTokenLatencyMs"),
                "reasoningContentPresent": bool(summary.get("reasoningContentPresent")),
                "toolCalls": [str(item) for item in tool_calls],
                "toolCallCount": len(tool_calls),
                "toolFailureCount": len(tool_failures),
            }
        )
    return records


def _work_tree_directives(text: str) -> list[dict[str, Any]]:
    directives: list[dict[str, Any]] = []
    for match in _WORK_DIRECTIVE_RE.finditer(text):
        attrs = {
            attr_match.group("name"): attr_match.group("value")
            for attr_match in _ATTR_RE.finditer(match.group("attrs") or "")
        }
        directives.append(
            {
                "tag": match.group("tag").lower(),
                "attrs": attrs,
                "bodyPreview": normalize_excerpt(match.group("body").strip(), 240),
            }
        )
    return directives


def _work_tree_natural_language_claims(text: str) -> list[str]:
    claims: list[str] = []
    for match in _WORK_NATURAL_LANGUAGE_CLAIM_RE.finditer(str(text or "")):
        claim = normalize_excerpt(str(match.group(0) or "").strip(), 120)
        if claim and claim not in claims:
            claims.append(claim)
    return claims[:8]


def _self_reported_tool_counts(assistant_text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for match in _SELF_REPORTED_TOOL_COUNT_RE.finditer(assistant_text):
        tool = match.group("tool")
        try:
            count = int(match.group("count"))
        except Exception:
            continue
        counts[str(tool)] = count
    return counts


def _tool_count_mismatches(actual_counts: Counter[str], reported_counts: dict[str, int]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for tool, reported in sorted(reported_counts.items()):
        actual = int(actual_counts.get(tool, 0))
        if actual != reported:
            mismatches.append({"toolName": tool, "reportedCount": reported, "actualCount": actual})
    return mismatches


def build_llm_behavior_record(
    *,
    workspace_root: Path,
    task: Any,
    run: Any,
    invocation: Any,
    prompt_artifact_id: str | None,
    request_path: Path | None,
    response_path: Path | None,
    prompt_path: Path | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    invocation_id = str(_value(invocation, "id") or "").strip()
    task_id = str(_value(task, "id") or "").strip()
    run_id = str(_value(run, "id") or "").strip()
    request_payload = _json_file(request_path)
    response_payload = _json_file(response_path)
    prompt_payload = _json_file(prompt_path)
    rounds = _round_records(response_payload)
    tools = _tool_records(response_payload)
    execution_tool_counts = Counter(record["toolName"] for record in tools)
    round_tool_counts = _round_tool_counts(rounds)
    observed_tool_counts = execution_tool_counts or round_tool_counts
    assistant_text = str(response_payload.get("assistantText") or "")
    reported_counts = _self_reported_tool_counts(assistant_text)
    work_tree_directives = _work_tree_directives(assistant_text)
    work_tree_claims = _work_tree_natural_language_claims(assistant_text)
    runtime_metrics = response_payload.get("runtimeMetrics") if isinstance(response_payload.get("runtimeMetrics"), dict) else {}
    prompt = prompt_payload.get("prompt") if isinstance(prompt_payload.get("prompt"), dict) else {}
    registered_tools = prompt.get("registeredTools") if isinstance(prompt.get("registeredTools"), list) else []
    request_tools = request_payload.get("tools") if isinstance(request_payload.get("tools"), list) else request_payload.get("toolSpecs")
    request_tools = request_tools if isinstance(request_tools, list) else []
    prompt_messages = [
        message
        for message in (prompt_payload.get("messages") or request_payload.get("initialMessages") or request_payload.get("messages") or [])
        if isinstance(message, dict)
    ]
    prompt_text = "\n".join(
        str(message.get("content") or "")
        for message in prompt_messages
    )
    message_digests = prompt_payload.get("messageDigests")
    if not isinstance(message_digests, list):
        message_digests = request_payload.get("initialMessageDigests") if isinstance(request_payload.get("initialMessageDigests"), list) else []
    message_count = len(prompt_messages)
    if message_count == 0:
        try:
            message_count = int(prompt_payload.get("messageCount") or len(message_digests))
        except Exception:
            message_count = len(message_digests)
    prompt_text_available = bool(prompt_text.strip())

    return {
        "artifactKind": "llm-behavior-record",
        "schemaVersion": "0.1.0",
        "createdAt": utc_now().isoformat(),
        "invocationId": invocation_id,
        "taskId": task_id,
        "projectId": _value(task, "project_id"),
        "agentRunId": run_id,
        "status": status or _value(invocation, "status") or response_payload.get("status"),
        "promptCompileArtifactId": prompt_artifact_id,
        "artifactRefs": {
            "request": _path_locator(request_path, workspace_root),
            "response": _path_locator(response_path, workspace_root),
            "compiledPrompt": _path_locator(prompt_path, workspace_root),
        },
        "prompt": {
            "messageCount": message_count,
            "messageDigestCount": len(message_digests),
            "textAvailable": prompt_text_available,
            "registeredToolCount": len(registered_tools),
            "requestToolSpecCount": len(request_tools),
            "containsWorkTreeCases": bool(prompt_text_available and "工作树使用案例" in prompt_text),
            "containsRootLeafGuidance": bool(
                prompt_text_available and ("根节点和非叶子节点" in prompt_text or "叶子节点" in prompt_text)
            ),
        },
        "runtime": {
            "windowIndex": runtime_metrics.get("windowIndex"),
            "restartCount": runtime_metrics.get("restartCount"),
            "cumulativeWindowSpanTokens": runtime_metrics.get("cumulativeWindowSpanTokens"),
        },
        "rounds": rounds,
        "toolExecutions": tools,
        "assistantBehavior": {
            "assistantTextPreview": normalize_excerpt(assistant_text, 500),
            "workTreeDirectives": work_tree_directives,
            "workTreeNaturalLanguageClaims": work_tree_claims,
            "workTreeClaimWithoutDirective": bool(work_tree_claims and not work_tree_directives),
            "selfReportedToolCounts": reported_counts,
        },
        "integrity": {
            "roundCount": len(rounds),
            "toolExecutionCount": len(tools),
            "observedToolCallCount": sum(round_tool_counts.values()),
            "toolEvidenceSource": "toolExecutions" if tools else ("rounds.toolCalls" if round_tool_counts else "none"),
            "successfulToolExecutionCount": sum(1 for record in tools if bool(record.get("success"))),
            "failedToolExecutionCount": sum(1 for record in tools if not bool(record.get("success"))),
            "executionToolCounts": dict(sorted(execution_tool_counts.items())),
            "roundToolCounts": dict(sorted(round_tool_counts.items())),
            "actualToolCounts": dict(sorted(observed_tool_counts.items())),
            "assistantSelfReportToolCountMismatches": _tool_count_mismatches(observed_tool_counts, reported_counts),
            "assistantSelfReportHasToolCounts": bool(reported_counts),
        },
    }


def persist_llm_behavior_record(
    *,
    workspace_root: Path,
    task: Any,
    run: Any,
    invocation: Any,
    prompt_artifact_id: str | None,
    request_path: Path | None,
    response_path: Path | None,
    prompt_path: Path | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    invocation_id = str(_value(invocation, "id") or "").strip()
    if not invocation_id:
        raise ValueError("Cannot persist LLM behavior record without invocation id.")
    if prompt_path is None:
        prompt_path = _state_dir(workspace_root) / "prompt" / "compiled" / f"{invocation_id}.json"
    record = build_llm_behavior_record(
        workspace_root=workspace_root,
        task=task,
        run=run,
        invocation=invocation,
        prompt_artifact_id=prompt_artifact_id,
        request_path=request_path,
        response_path=response_path,
        prompt_path=prompt_path,
        status=status,
    )
    behavior_dir = _state_dir(workspace_root) / "llm" / "behavior-records"
    behavior_dir.mkdir(parents=True, exist_ok=True)
    record_path = behavior_dir / f"{invocation_id}.json"
    write_json(record_path, record)

    task_id = str(record.get("taskId") or "").strip()
    if task_id:
        by_task_dir = behavior_dir / "by-task"
        by_task_dir.mkdir(parents=True, exist_ok=True)
        task_record_path = by_task_dir / f"task_{task_id}.json"
        task_payload = read_json(task_record_path, None)
        if not isinstance(task_payload, dict):
            task_payload = {"artifactKind": "llm-behavior-record-index", "schemaVersion": "0.1.0", "taskId": task_id, "records": []}
        records = [
            item
            for item in (task_payload.get("records") or [])
            if isinstance(item, dict) and str(item.get("invocationId") or "") != invocation_id
        ]
        records.append(
            {
                "invocationId": invocation_id,
                "agentRunId": record.get("agentRunId"),
                "status": record.get("status"),
                "createdAt": record.get("createdAt"),
                "recordRef": _path_locator(record_path, workspace_root),
                "toolExecutionCount": record["integrity"]["toolExecutionCount"],
                "observedToolCallCount": record["integrity"]["observedToolCallCount"],
                "workTreeDirectiveCount": len(record["assistantBehavior"]["workTreeDirectives"]),
                "workTreeClaimWithoutDirective": bool(record["assistantBehavior"].get("workTreeClaimWithoutDirective")),
            }
        )
        records.sort(key=lambda item: str(item.get("createdAt") or ""))
        task_payload["updatedAt"] = utc_now().isoformat()
        task_payload["recordCount"] = len(records)
        task_payload["records"] = records
        write_json(task_record_path, task_payload)

    return {
        "behaviorRecordRef": {"type": "file", "locator": _path_locator(record_path, workspace_root)},
        "summary": {
            "invocationId": invocation_id,
            "toolExecutionCount": record["integrity"]["toolExecutionCount"],
            "observedToolCallCount": record["integrity"]["observedToolCallCount"],
            "roundCount": record["integrity"]["roundCount"],
            "assistantSelfReportToolCountMismatches": record["integrity"]["assistantSelfReportToolCountMismatches"],
            "workTreeDirectiveCount": len(record["assistantBehavior"]["workTreeDirectives"]),
            "workTreeClaimWithoutDirective": bool(record["assistantBehavior"].get("workTreeClaimWithoutDirective")),
        },
    }


__all__ = [name for name in globals() if not name.startswith("__")]
