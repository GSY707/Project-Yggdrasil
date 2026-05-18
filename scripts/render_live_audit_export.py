from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
import re
from typing import Any


FAILURE_PATTERN = re.compile(
    r"(?P<metric>[A-Za-z0-9_]+)\s+(?P<kind>不足|超限): actual=(?P<actual>[^,;|]+), expected(?P<op><=|>=)(?P<expected>[^;|]+)"
)
SANDBOX_PATTERN = re.compile(r"sandbox=.*?[\\/](evalsandbox_[A-Za-z0-9]+)")
SECTION_PATTERN = re.compile(r"^##\s+\d+\.\s+(.+)$", re.MULTILINE)

LANGFUSE_UI = "http://127.0.0.1:3100"
LANGFUSE_LOGIN_EMAIL = "admin@example.com"
LANGFUSE_LOGIN_PASSWORD = "LangfuseLocal123!"
LANGFUSE_PUBLIC_KEY = "pk-lf-yggdrasil-local"
LANGFUSE_SECRET_KEY = "sk-lf-yggdrasil-local-secret"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(json.loads(line))
    return records


def _compact(value: str | None) -> str:
    return " ".join((value or "").split())


def _excerpt(value: str | None, limit: int = 640) -> str:
    compact = _compact(value)
    if len(compact) <= limit:
        return compact
    return compact[: max(limit - 1, 1)].rstrip() + "..."


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _markdown_link(path: Path | None, root: Path, label: str) -> str:
    if path is None or not path.exists():
        return f"{label}: missing"
    return f"[{label}]({_relative(path, root)})"


def _html_link(path: Path | None, root: Path, label: str) -> str:
    if path is None or not path.exists():
        return f"<span class=\"missing\">{escape(label)}: missing</span>"
    relative = escape(_relative(path, root))
    return f"<a href=\"{relative}\">{escape(label)}</a>"


def _load_window_records(window_dir: Path) -> list[dict[str, Any]]:
    if not window_dir.exists():
        return []
    records = [_read_json(path) for path in sorted(window_dir.glob("*.json"))]
    return sorted(records, key=lambda item: (item.get("windowIndex") or -1, item.get("createdAt") or ""))


def _parse_failures(error_text: str) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for match in FAILURE_PATTERN.finditer(error_text or ""):
        failures.append(
            {
                "metric": match.group("metric"),
                "kind": match.group("kind"),
                "actual": match.group("actual").strip(),
                "op": match.group("op"),
                "expected": match.group("expected").strip(),
            }
        )
    return failures


def _extract_sandbox_id(error_text: str) -> str | None:
    match = SANDBOX_PATTERN.search(error_text or "")
    return match.group(1) if match else None


def _discover_first_json(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob("*.json"))
    return files[0] if files else None


def _discover_case_assets(export_root: Path, sandbox_id: str | None) -> dict[str, Path | None]:
    if sandbox_id is None:
        return {
            "sandbox_root": None,
            "request_file": None,
            "response_file": None,
            "prompt_file": None,
            "window_dir": None,
            "spans_file": None,
            "metrics_file": None,
            "outbox_dir": None,
            "mcp_bridge_dir": None,
            "evaluation_db": None,
        }
    sandbox_root = export_root / "sandboxes" / sandbox_id
    state_root = sandbox_root / ".yggdrasil" / "state"
    return {
        "sandbox_root": sandbox_root,
        "request_file": _discover_first_json(state_root / "llm" / "requests"),
        "response_file": _discover_first_json(state_root / "llm" / "responses"),
        "prompt_file": _discover_first_json(state_root / "prompt" / "compiled"),
        "window_dir": state_root / "runtime" / "window-executions",
        "spans_file": state_root / "observability" / "spans.jsonl",
        "metrics_file": state_root / "observability" / "metrics.jsonl",
        "outbox_dir": state_root / "outbox-payloads",
        "mcp_bridge_dir": state_root / "mcp-bridge",
        "evaluation_db": sandbox_root / "evaluation.db",
    }


def _file_size(path: Path | None) -> int | None:
    return path.stat().st_size if path and path.exists() else None


def _format_number(value: int | float | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return f"{value:,}"


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("T", " ").replace("+00:00", " UTC")


def _build_memory_tree_preview(latest_window: dict[str, Any] | None) -> str:
    if not latest_window:
        return "No window execution records found."
    retrieval = latest_window.get("memoryRetrievalState") or {}
    work_tree_node = (
        retrieval.get("workTreeNodeId")
        or latest_window.get("workTreeCurrentNodeId")
        or latest_window.get("createdExecutionNodeId")
        or "work-tree-node:missing"
    )
    lines = [str(work_tree_node)]
    request_id = retrieval.get("requestId") or "retrieval-request:missing"
    lines.append(f"└─ retrieval {request_id}")
    matched_ids = retrieval.get("matchedNodeIds") or []
    if matched_ids:
        for index, node_id in enumerate(matched_ids):
            branch = "└─" if index == len(matched_ids) - 1 else "├─"
            lines.append(f"   {branch} {node_id}")
    else:
        lines.append("   └─ no matched node ids persisted")
    titles = latest_window.get("currentContextTitlesPreview") or []
    if titles:
        lines.append("current-context-preview")
        for title in titles:
            lines.append(f"  - {title}")
    return "\n".join(lines)


def _window_tail_rows(window_records: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in window_records[-limit:]:
        retrieval = record.get("memoryRetrievalState") or {}
        rows.append(
            {
                "windowIndex": record.get("windowIndex"),
                "restartCount": record.get("restartCount"),
                "matchedNodeCount": retrieval.get("matchedNodeCount"),
                "currentContextCount": record.get("currentContextCount"),
                "titles": ", ".join((record.get("currentContextTitlesPreview") or [])[:3]),
                "workTreeNodeId": retrieval.get("workTreeNodeId") or record.get("workTreeCurrentNodeId"),
            }
        )
    return rows


def _collect_trace_summary(spans: list[dict[str, Any]]) -> dict[str, Any]:
    if not spans:
        return {
            "traceId": None,
            "spanCount": 0,
            "serviceCounts": {},
            "llmSpan": None,
            "topSpans": [],
        }
    service_counts = Counter(span.get("serviceName") or "unknown" for span in spans)
    llm_span = next((span for span in spans if span.get("name") == "llm.chat.completion"), None)
    top_spans = sorted(spans, key=lambda span: span.get("durationMs") or 0, reverse=True)[:5]
    return {
        "traceId": spans[0].get("traceId"),
        "spanCount": len(spans),
        "serviceCounts": dict(service_counts),
        "llmSpan": llm_span,
        "topSpans": top_spans,
    }


def _focus_hints(failures: list[dict[str, str]]) -> list[str]:
    hints: list[str] = []
    metrics = {failure["metric"] for failure in failures}
    if "workTreeContinuity0_1" in metrics:
        hints.append("先看最后 3 个 window-executions：workTreeNodeId、currentContextTitlesPreview、responseRequirementsDigest 是否稳定。")
    if "retrievalDriftRate0_1" in metrics:
        hints.append("对比最后几个窗口的 matchedNodeIds 与 currentContextTitlesPreview，检查检索锚点是否在恢复后漂移。")
    if "cumulativeWindowSpanTokens" in metrics:
        hints.append("检查 response.runtimeMetrics 与 contextLengthObservations，确认最小工作集路径是否过早收束。")
    if not hints:
        hints.append("从 request/response/prompt 三件套开始，再顺着 spans.jsonl 对照时序。")
    return hints


def _failure_summary(failure: dict[str, str]) -> str:
    if failure["kind"] == "不足" and failure["op"] == ">=":
        comparator = "<"
    elif failure["kind"] == "超限" and failure["op"] == "<=":
        comparator = ">"
    else:
        comparator = failure["op"]
    return f"{failure['metric']} {failure['actual']} {comparator} {failure['expected']}"


def _build_case_summary(export_root: Path, case_entry: dict[str, Any]) -> dict[str, Any]:
    error_text = (case_entry.get("detail") or {}).get("error") or ""
    sandbox_id = _extract_sandbox_id(error_text)
    assets = _discover_case_assets(export_root, sandbox_id)
    request = _read_json(assets["request_file"]) if assets["request_file"] else {}
    response = _read_json(assets["response_file"]) if assets["response_file"] else {}
    prompt = _read_json(assets["prompt_file"]) if assets["prompt_file"] else {}
    window_records = _load_window_records(assets["window_dir"]) if assets["window_dir"] else []
    latest_window = window_records[-1] if window_records else None
    spans = _read_jsonl(assets["spans_file"]) if assets["spans_file"] else []
    trace_summary = _collect_trace_summary(spans)
    outbox_count = len(list((assets["outbox_dir"] or Path()).glob("*.json"))) if assets["outbox_dir"] and assets["outbox_dir"].exists() else 0
    prompt_metadata = request.get("promptMetadata") or {}
    usage = response.get("usage") or {}
    runtime_metrics = response.get("runtimeMetrics") or {}
    assistant_text = response.get("assistantText") or ""
    failures = _parse_failures(error_text)
    sections = SECTION_PATTERN.findall(assistant_text)

    return {
        "id": case_entry.get("id"),
        "title": case_entry.get("title"),
        "status": case_entry.get("status"),
        "durationMs": case_entry.get("durationMs"),
        "errorText": error_text,
        "failureMetrics": failures,
        "sandboxId": sandbox_id,
        "sandboxRoot": assets["sandbox_root"],
        "requestFile": assets["request_file"],
        "responseFile": assets["response_file"],
        "promptFile": assets["prompt_file"],
        "windowDir": assets["window_dir"],
        "spansFile": assets["spans_file"],
        "metricsFile": assets["metrics_file"],
        "outboxDir": assets["outbox_dir"],
        "mcpBridgeDir": assets["mcp_bridge_dir"],
        "evaluationDb": assets["evaluation_db"],
        "requestSize": _file_size(assets["request_file"]),
        "responseSize": _file_size(assets["response_file"]),
        "promptSize": _file_size(assets["prompt_file"]),
        "provider": response.get("provider") or request.get("requestedProvider"),
        "model": response.get("model") or request.get("requestedModel"),
        "invocationId": response.get("invocationId") or request.get("invocationId"),
        "taskId": response.get("taskId") or request.get("taskId"),
        "agentRunId": response.get("agentRunId") or request.get("agentRunId"),
        "traceId": trace_summary.get("traceId"),
        "llmSpanMs": (trace_summary.get("llmSpan") or {}).get("durationMs"),
        "spanCount": trace_summary.get("spanCount"),
        "serviceCounts": trace_summary.get("serviceCounts"),
        "topSpans": trace_summary.get("topSpans"),
        "outboxCount": outbox_count,
        "promptProfileId": prompt_metadata.get("promptProfileId"),
        "seedTemplateId": prompt_metadata.get("seedTemplateId"),
        "registeredToolCount": len(prompt_metadata.get("registeredTools") or []),
        "responseRequirements": prompt.get("responseRequirements") or request.get("responseRequirements"),
        "restartMessage": prompt.get("restartMessage") or request.get("restartMessage"),
        "assistantSections": sections,
        "assistantTextExcerpt": _excerpt(assistant_text, limit=1200),
        "assistantTextLength": len(assistant_text),
        "usage": usage,
        "runtimeMetrics": runtime_metrics,
        "contextLengthObservations": response.get("contextLengthObservations") or [],
        "windowRecordCount": len(window_records),
        "memoryTreePreview": _build_memory_tree_preview(latest_window),
        "windowTail": _window_tail_rows(window_records),
        "latestWindow": latest_window,
        "focusHints": _focus_hints(failures),
    }


def _build_run_summary(export_root: Path, run_path: Path) -> dict[str, Any]:
    run = _read_json(run_path)
    case_summaries = [_build_case_summary(export_root, case_entry) for case_entry in run.get("cases") or []]
    failure_counter = Counter(
        failure["metric"]
        for case_summary in case_summaries
        for failure in case_summary.get("failureMetrics") or []
    )
    return {
        "suiteId": run.get("suiteId"),
        "suiteName": run.get("suiteName"),
        "runId": run.get("runId"),
        "status": run.get("status"),
        "caseCount": run.get("caseCount"),
        "passedCount": run.get("passedCount"),
        "failedCount": run.get("failedCount"),
        "passRate": run.get("passRate"),
        "totalDurationMs": run.get("totalDurationMs"),
        "generatedAt": run.get("generatedAt"),
        "traceId": run.get("traceId"),
        "evaluationFile": run_path,
        "dominantFailures": failure_counter.most_common(4),
        "cases": case_summaries,
    }


def _collect_report(export_root: Path) -> dict[str, Any]:
    evaluation_dir = export_root / "evaluations"
    run_paths = sorted(evaluation_dir.glob("evalrun_*.json"))
    runs = [_build_run_summary(export_root, path) for path in run_paths]
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exportRoot": export_root,
        "runCount": len(runs),
        "caseCount": sum(len(run["cases"]) for run in runs),
        "runs": runs,
    }


def _render_markdown(report: dict[str, Any], output_path: Path) -> str:
    export_root: Path = report["exportRoot"]
    lines: list[str] = []
    lines.append("# G4 Live Audit Human-Readable Report")
    lines.append("")
    lines.append(f"生成时间：{report['generatedAt']}")
    lines.append("")
    lines.append("## 快速入口")
    lines.append("")
    lines.append(f"- 离线浏览页：[viewer.html](viewer.html)")
    lines.append(f"- 原始索引：[INDEX.md](INDEX.md)")
    lines.append(f"- 当前人类可读报告：[{output_path.name}]({output_path.name})")
    lines.append("")
    lines.append("## Langfuse 本地登录")
    lines.append("")
    lines.append(f"- UI：{LANGFUSE_UI}")
    lines.append(f"- 登录邮箱：{LANGFUSE_LOGIN_EMAIL}")
    lines.append(f"- 登录密码：{LANGFUSE_LOGIN_PASSWORD}")
    lines.append(f"- Public key：{LANGFUSE_PUBLIC_KEY}")
    lines.append(f"- Secret key：{LANGFUSE_SECRET_KEY}")
    lines.append("- 启动命令：pnpm infra:langfuse:up")
    lines.append("- 停止命令：pnpm infra:langfuse:down")
    lines.append("- 这份导出包已经保留了离线 spans/outbox/request/response，所以即便 Langfuse 当时没开，你也能先做线下分析，再用 traceId 去 UI 里搜索。")
    lines.append("")
    lines.append("## 总览")
    lines.append("")
    lines.append("| Suite | Run | Pass Rate | Failed | Dominant Blockers |")
    lines.append("| --- | --- | ---: | ---: | --- |")
    for run in report["runs"]:
        blockers = ", ".join(f"{metric} x{count}" for metric, count in run["dominantFailures"]) or "-"
        evaluation_link = _relative(run["evaluationFile"], export_root)
        lines.append(
            f"| {run['suiteName']} | [{run['runId']}]({evaluation_link}) | {run['passRate']} | {run['failedCount']} | {blockers} |"
        )
    lines.append("")
    for run in report["runs"]:
        lines.append(f"## {run['suiteName']}")
        lines.append("")
        lines.append(f"- runId：{run['runId']}")
        lines.append(f"- 状态：{run['status']}")
        lines.append(f"- passRate：{run['passRate']}")
        lines.append(f"- 失败数：{run['failedCount']} / {run['caseCount']}")
        lines.append(f"- traceId：{run['traceId'] or '-'}")
        lines.append(f"- 运行结果 JSON：{_markdown_link(run['evaluationFile'], export_root, run['evaluationFile'].name)}")
        dominant = ", ".join(f"{metric} x{count}" for metric, count in run["dominantFailures"]) or "-"
        lines.append(f"- 主导失败项：{dominant}")
        lines.append("")
        lines.append("| Case | Provider | Restarts | Final Window | Span Tokens | Main Failures |")
        lines.append("| --- | --- | ---: | ---: | ---: | --- |")
        for case in run["cases"]:
            runtime_metrics = case["runtimeMetrics"]
            failures = ", ".join(_failure_summary(failure) for failure in case["failureMetrics"]) or "-"
            lines.append(
                f"| {case['title']} | {case['provider']} / {case['model']} | {runtime_metrics.get('restartCount', '-')} | {runtime_metrics.get('windowIndex', '-')} | {runtime_metrics.get('cumulativeWindowSpanTokens', '-')} | {failures} |"
            )
        lines.append("")
        for case in run["cases"]:
            runtime_metrics = case["runtimeMetrics"]
            lines.append(f"### {case['title']}")
            lines.append("")
            lines.append(f"- caseId：{case['id']}")
            lines.append(f"- 状态：{case['status']}")
            lines.append(f"- provider/model：{case['provider']} / {case['model']}")
            lines.append(f"- sandbox：{case['sandboxId'] or '-'}")
            lines.append(f"- traceId：{case['traceId'] or '-'}")
            lines.append(f"- invocationId：{case['invocationId'] or '-'}")
            lines.append(f"- taskId：{case['taskId'] or '-'}")
            lines.append(f"- agentRunId：{case['agentRunId'] or '-'}")
            lines.append(f"- durationMs：{_format_number(case['durationMs'])}")
            lines.append(f"- llm.chat.completion span：{_format_number(case['llmSpanMs'])} ms")
            lines.append(f"- restartCount：{runtime_metrics.get('restartCount', '-')}")
            lines.append(f"- final windowIndex：{runtime_metrics.get('windowIndex', '-')}")
            lines.append(f"- cumulativeWindowSpanTokens：{runtime_metrics.get('cumulativeWindowSpanTokens', '-')}")
            lines.append(f"- toolExecutionCount：{len((response := _read_json(case['responseFile'])) .get('toolExecutions') or []) if case['responseFile'] else '-'}")
            lines.append(f"- outbox event 数：{case['outboxCount']}")
            lines.append(f"- prompt profile：{case['promptProfileId'] or '-'}")
            lines.append(f"- seed template：{case['seedTemplateId'] or '-'}")
            lines.append(f"- 注册工具数：{case['registeredToolCount']}")
            lines.append("")
            lines.append("失败指标：")
            if case["failureMetrics"]:
                for failure in case["failureMetrics"]:
                    lines.append(
                        f"- {failure['metric']}：actual={failure['actual']}，要求 {failure['op']} {failure['expected']}（{failure['kind']}）"
                    )
            else:
                lines.append("- 无结构化失败指标，直接查看 errorText。")
            lines.append("")
            lines.append("建议先看的点：")
            for hint in case["focusHints"]:
                lines.append(f"- {hint}")
            lines.append("")
            lines.append("离线证据入口：")
            lines.append(f"- {_markdown_link(case['requestFile'], export_root, 'request JSON')}")
            lines.append(f"- {_markdown_link(case['responseFile'], export_root, 'response JSON')}")
            lines.append(f"- {_markdown_link(case['promptFile'], export_root, 'compiled prompt')}")
            lines.append(f"- {_markdown_link(case['spansFile'], export_root, 'spans.jsonl')}")
            lines.append(f"- {_markdown_link(case['metricsFile'], export_root, 'metrics.jsonl')}")
            lines.append(f"- {_markdown_link(case['evaluationDb'], export_root, 'evaluation.db')}")
            if case["windowDir"] and case["windowDir"].exists():
                lines.append(f"- [window-executions dir]({_relative(case['windowDir'], export_root)})")
            if case["outboxDir"] and case["outboxDir"].exists():
                lines.append(f"- [outbox-payloads dir]({_relative(case['outboxDir'], export_root)})")
            if case["mcpBridgeDir"] and case["mcpBridgeDir"].exists():
                lines.append(f"- [mcp-bridge dir]({_relative(case['mcpBridgeDir'], export_root)})")
            lines.append("")
            lines.append("响应结构：")
            lines.append(f"- 命中的 Markdown section：{', '.join(case['assistantSections']) or '-'}")
            lines.append(f"- 响应摘要：{case['assistantTextExcerpt']}")
            lines.append("")
            lines.append("近似记忆树 / 工作树视图：")
            lines.append("")
            lines.append("```text")
            lines.append(case["memoryTreePreview"])
            lines.append("```")
            lines.append("")
            lines.append("窗口尾部时间线：")
            lines.append("")
            lines.append("| Window | Restart | Matched Nodes | Context Count | Work Tree Node | Context Preview |")
            lines.append("| --- | ---: | ---: | ---: | --- | --- |")
            for row in case["windowTail"]:
                lines.append(
                    f"| {row['windowIndex']} | {row['restartCount']} | {row['matchedNodeCount']} | {row['currentContextCount']} | {row['workTreeNodeId'] or '-'} | {row['titles'] or '-'} |"
                )
            lines.append("")
    return "\n".join(lines) + "\n"


def _render_case_card(case: dict[str, Any], export_root: Path) -> str:
    runtime_metrics = case["runtimeMetrics"]
    failure_items = "".join(
        f"<li><strong>{escape(failure['metric'])}</strong> <span class=\"metric-kind\">{escape(failure['kind'])}</span>"
        f"<span class=\"metric-value\">actual {escape(failure['actual'])}</span>"
        f"<span class=\"metric-value\">expected {escape(failure['op'])} {escape(failure['expected'])}</span></li>"
        for failure in case["failureMetrics"]
    ) or "<li>没有解析出结构化失败指标，请直接查看 errorText 或 response JSON。</li>"
    hint_items = "".join(f"<li>{escape(hint)}</li>" for hint in case["focusHints"])
    window_rows = "".join(
        "<tr>"
        f"<td>{escape(str(row['windowIndex']))}</td>"
        f"<td>{escape(str(row['restartCount']))}</td>"
        f"<td>{escape(str(row['matchedNodeCount']))}</td>"
        f"<td>{escape(str(row['currentContextCount']))}</td>"
        f"<td>{escape(row['workTreeNodeId'] or '-')}</td>"
        f"<td>{escape(row['titles'] or '-')}</td>"
        "</tr>"
        for row in case["windowTail"]
    )
    span_rows = "".join(
        "<tr>"
        f"<td>{escape(span.get('serviceName') or '-')}</td>"
        f"<td>{escape(span.get('name') or '-')}</td>"
        f"<td>{escape(_format_number(span.get('durationMs')))}</td>"
        "</tr>"
        for span in case["topSpans"]
    )
    links = [
        _html_link(case["requestFile"], export_root, "request JSON"),
        _html_link(case["responseFile"], export_root, "response JSON"),
        _html_link(case["promptFile"], export_root, "compiled prompt"),
        _html_link(case["spansFile"], export_root, "spans.jsonl"),
        _html_link(case["metricsFile"], export_root, "metrics.jsonl"),
        _html_link(case["evaluationDb"], export_root, "evaluation.db"),
    ]
    if case["windowDir"] and case["windowDir"].exists():
        links.append(_html_link(case["windowDir"], export_root, "window-executions dir"))
    if case["outboxDir"] and case["outboxDir"].exists():
        links.append(_html_link(case["outboxDir"], export_root, "outbox-payloads dir"))
    if case["mcpBridgeDir"] and case["mcpBridgeDir"].exists():
        links.append(_html_link(case["mcpBridgeDir"], export_root, "mcp-bridge dir"))
    link_html = "".join(f"<li>{link}</li>" for link in links)
    search_blob = " ".join(
        filter(
            None,
            [
                case["title"],
                case["id"],
                case["provider"],
                case["model"],
                case["traceId"],
                " ".join(failure["metric"] for failure in case["failureMetrics"]),
            ],
        )
    ).lower()
    return (
        f"<details class=\"case-card\" data-search=\"{escape(search_blob)}\" data-provider=\"{escape((case['provider'] or '').lower())}\" "
        f"data-status=\"{escape((case['status'] or '').lower())}\">"
        "<summary>"
        f"<span class=\"case-title\">{escape(case['title'] or '')}</span>"
        f"<span class=\"badge status-{escape((case['status'] or '').lower())}\">{escape(case['status'] or '-')}</span>"
        f"<span class=\"badge\">{escape(case['provider'] or '-')}</span>"
        f"<span class=\"badge\">restart {escape(str(runtime_metrics.get('restartCount', '-')))}</span>"
        f"<span class=\"badge\">window {escape(str(runtime_metrics.get('windowIndex', '-')))}</span>"
        "</summary>"
        "<div class=\"case-grid\">"
        "<section class=\"panel\">"
        "<h4>失败指标</h4>"
        f"<ul class=\"metric-list\">{failure_items}</ul>"
        "<h4>优先排查</h4>"
        f"<ul>{hint_items}</ul>"
        "<h4>Langfuse / Trace 对照</h4>"
        f"<p><strong>traceId</strong> {escape(case['traceId'] or '-')}</p>"
        f"<p><strong>invocationId</strong> {escape(case['invocationId'] or '-')}</p>"
        f"<p><strong>taskId</strong> {escape(case['taskId'] or '-')}</p>"
        f"<p><strong>agentRunId</strong> {escape(case['agentRunId'] or '-')}</p>"
        f"<p><strong>llm.chat.completion</strong> {_format_number(case['llmSpanMs'])} ms</p>"
        "</section>"
        "<section class=\"panel\">"
        "<h4>离线证据入口</h4>"
        f"<ul>{link_html}</ul>"
        "<h4>关键运行指标</h4>"
        f"<p>cumulativeWindowSpanTokens {_format_number(runtime_metrics.get('cumulativeWindowSpanTokens'))}</p>"
        f"<p>effectiveContextWindow {_format_number(runtime_metrics.get('effectiveContextWindow'))}</p>"
        f"<p>toolExecutionCount {escape(str(len((_read_json(case['responseFile']).get('toolExecutions') or []) if case['responseFile'] else [])))} | outbox {case['outboxCount']}</p>"
        f"<p>prompt profile {escape(case['promptProfileId'] or '-')} | seed {escape(case['seedTemplateId'] or '-')}</p>"
        f"<p>files request {_format_number(case['requestSize'])} B / response {_format_number(case['responseSize'])} B / prompt {_format_number(case['promptSize'])} B</p>"
        "</section>"
        "</div>"
        "<div class=\"panel\">"
        "<h4>近似记忆树 / 工作树视图</h4>"
        f"<pre>{escape(case['memoryTreePreview'])}</pre>"
        "</div>"
        "<div class=\"panel\">"
        "<h4>窗口尾部时间线</h4>"
        "<table><thead><tr><th>Window</th><th>Restart</th><th>Matched</th><th>Context</th><th>Work Tree</th><th>Preview</th></tr></thead>"
        f"<tbody>{window_rows}</tbody></table>"
        "</div>"
        "<div class=\"panel\">"
        "<h4>Top Spans</h4>"
        "<table><thead><tr><th>Service</th><th>Name</th><th>Duration ms</th></tr></thead>"
        f"<tbody>{span_rows}</tbody></table>"
        "</div>"
        "<div class=\"panel response-panel\">"
        "<h4>响应摘录</h4>"
        f"<p class=\"response-copy\">{escape(case['assistantTextExcerpt'])}</p>"
        "</div>"
        "</details>"
    )


def _render_html(report: dict[str, Any]) -> str:
    export_root: Path = report["exportRoot"]
    run_cards: list[str] = []
    for run in report["runs"]:
        case_cards = "".join(_render_case_card(case, export_root) for case in run["cases"])
        blockers = "".join(
            f"<li><strong>{escape(metric)}</strong> x{count}</li>" for metric, count in run["dominantFailures"]
        ) or "<li>无</li>"
        run_cards.append(
            "<section class=\"run-section\">"
            f"<div class=\"run-header\"><div><h2>{escape(run['suiteName'] or '')}</h2>"
            f"<p>runId {escape(run['runId'] or '')} | traceId {escape(run['traceId'] or '-')}</p></div>"
            f"<div class=\"run-stats\"><span class=\"stat\">passRate {escape(str(run['passRate']))}</span>"
            f"<span class=\"stat\">failed {escape(str(run['failedCount']))}/{escape(str(run['caseCount']))}</span>"
            f"<span class=\"stat\">duration {_format_number(run['totalDurationMs'])} ms</span></div></div>"
            f"<div class=\"panel\"><h4>Dominant blockers</h4><ul class=\"blocker-list\">{blockers}</ul>"
            f"<p>{_html_link(run['evaluationFile'], export_root, 'evaluation JSON')}</p></div>"
            f"<div class=\"case-list\">{case_cards}</div>"
            "</section>"
        )
    return f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>G4 Live Audit Viewer</title>
  <style>
    :root {{
      --paper: #f5efe2;
      --ink: #15221d;
      --muted: #5a6b64;
      --teal: #0f766e;
      --rust: #a44a1d;
      --gold: #c38e2a;
      --line: rgba(21, 34, 29, 0.12);
      --card: rgba(255, 252, 246, 0.92);
      --shadow: 0 20px 60px rgba(25, 32, 28, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI Variable", "Microsoft YaHei UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(195, 142, 42, 0.18), transparent 28%),
        radial-gradient(circle at top right, rgba(15, 118, 110, 0.18), transparent 32%),
        linear-gradient(180deg, #f4ecdf 0%, #efe4d1 100%);
    }}
    main {{ max-width: 1440px; margin: 0 auto; padding: 32px 24px 80px; }}
    .hero {{
      display: grid;
      grid-template-columns: 2fr 1fr;
      gap: 18px;
      margin-bottom: 24px;
    }}
    .hero-card, .panel, .run-section, .toolbar {{
      background: var(--card);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      border-radius: 24px;
    }}
    .hero-card {{ padding: 28px; }}
    .hero h1 {{ margin: 0 0 10px; font-size: 42px; line-height: 1.05; letter-spacing: -0.03em; }}
    .hero p {{ margin: 0; color: var(--muted); line-height: 1.6; }}
    .hero-metrics {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 18px; }}
    .metric-box {{ border: 1px solid var(--line); border-radius: 16px; padding: 14px; background: rgba(255,255,255,0.5); }}
    .metric-box strong {{ display: block; font-size: 28px; }}
    .toolbar {{ position: sticky; top: 12px; z-index: 10; display: flex; gap: 12px; padding: 14px 16px; margin-bottom: 24px; backdrop-filter: blur(12px); }}
    .toolbar input, .toolbar select {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 12px 16px;
      background: rgba(255,255,255,0.86);
      font: inherit;
      color: inherit;
    }}
    .toolbar input {{ flex: 1; }}
    .run-section {{ padding: 22px; margin-bottom: 22px; }}
    .run-header {{ display: flex; justify-content: space-between; gap: 16px; align-items: start; }}
    .run-header h2 {{ margin: 0; font-size: 28px; }}
    .run-header p {{ margin: 6px 0 0; color: var(--muted); }}
    .run-stats {{ display: flex; gap: 8px; flex-wrap: wrap; }}
    .stat, .badge {{
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 8px 12px;
      background: rgba(21,34,29,0.06);
      border: 1px solid var(--line);
      font-size: 13px;
    }}
    .status-failed {{ background: rgba(164,74,29,0.14); border-color: rgba(164,74,29,0.28); color: #6e2407; }}
    .status-passed {{ background: rgba(15,118,110,0.14); border-color: rgba(15,118,110,0.28); color: #0b5b55; }}
    .panel {{ padding: 18px 20px; margin-top: 14px; }}
    .panel h3, .panel h4 {{ margin: 0 0 12px; }}
    .case-list {{ display: grid; gap: 14px; margin-top: 16px; }}
    .case-card {{ border: 1px solid var(--line); border-radius: 18px; background: rgba(255,255,255,0.45); overflow: hidden; }}
    .case-card[hidden] {{ display: none; }}
    .case-card summary {{ list-style: none; cursor: pointer; padding: 16px 18px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }}
    .case-card summary::-webkit-details-marker {{ display: none; }}
    .case-title {{ flex: 1 1 420px; font-size: 18px; font-weight: 700; }}
    .case-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; padding: 0 18px 6px; }}
    .metric-list, .blocker-list {{ margin: 0; padding-left: 18px; }}
    .metric-list li, .blocker-list li {{ margin: 6px 0; }}
    .metric-kind {{ color: var(--rust); margin-left: 8px; margin-right: 8px; }}
    .metric-value {{ color: var(--muted); margin-right: 10px; }}
    .response-panel {{ margin: 0 18px 18px; }}
    pre {{ margin: 0; padding: 16px; border-radius: 16px; overflow-x: auto; background: #151a18; color: #f6efe0; font-family: "Cascadia Code", "Consolas", monospace; }}
    table {{ width: 100%; border-collapse: collapse; }}
    th, td {{ text-align: left; padding: 10px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .response-copy {{ line-height: 1.75; color: var(--ink); }}
    .missing {{ color: var(--rust); }}
    a {{ color: var(--teal); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    @media (max-width: 980px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .case-grid {{ grid-template-columns: 1fr; }}
      .toolbar {{ position: static; flex-direction: column; }}
      .hero h1 {{ font-size: 34px; }}
    }}
  </style>
</head>
<body>
  <main>
    <section class=\"hero\">
      <div class=\"hero-card\">
        <p>离线导出浏览器</p>
        <h1>G4 Live Audit Viewer</h1>
        <p>这是针对 tmp/g4-live-audit-export-20260518 的自包含阅读页。它把 evaluation 结论、request/response、window-executions、spans 与 outbox 入口放在同一层，方便先做离线分析，再回到 Langfuse UI 里对照 trace。</p>
        <div class=\"hero-metrics\">
          <div class=\"metric-box\"><span>Runs</span><strong>{report['runCount']}</strong></div>
          <div class=\"metric-box\"><span>Cases</span><strong>{report['caseCount']}</strong></div>
          <div class=\"metric-box\"><span>Generated</span><strong style=\"font-size:18px\">{escape(report['generatedAt'])}</strong></div>
        </div>
      </div>
      <div class=\"hero-card\">
        <h3>Langfuse 快速登录</h3>
        <p><strong>UI</strong> {LANGFUSE_UI}</p>
        <p><strong>Email</strong> {LANGFUSE_LOGIN_EMAIL}</p>
        <p><strong>Password</strong> {LANGFUSE_LOGIN_PASSWORD}</p>
        <p><strong>Public key</strong> {LANGFUSE_PUBLIC_KEY}</p>
        <p><strong>Secret key</strong> {LANGFUSE_SECRET_KEY}</p>
        <p><strong>启动</strong> pnpm infra:langfuse:up</p>
        <p style=\"color: var(--muted);\">如果 UI 里一时找不到对象，先用这里展示的 traceId 去搜索；若本地观测未入库，也可以直接打开 spans.jsonl 做同源核对。</p>
      </div>
    </section>
    <section class=\"toolbar\">
      <input id=\"search\" type=\"search\" placeholder=\"按 case 名、provider、traceId、metric 搜索\" />
      <select id=\"providerFilter\">
        <option value=\"\">全部 provider</option>
        <option value=\"longcat\">longcat</option>
        <option value=\"deepseek_direct\">deepseek_direct</option>
      </select>
      <select id=\"statusFilter\">
        <option value=\"\">全部状态</option>
        <option value=\"failed\">failed</option>
        <option value=\"passed\">passed</option>
      </select>
    </section>
    {''.join(run_cards)}
  </main>
  <script>
    const searchInput = document.getElementById('search');
    const providerFilter = document.getElementById('providerFilter');
    const statusFilter = document.getElementById('statusFilter');
    const cards = Array.from(document.querySelectorAll('.case-card'));

    function applyFilters() {{
      const query = (searchInput.value || '').trim().toLowerCase();
      const provider = (providerFilter.value || '').trim().toLowerCase();
      const status = (statusFilter.value || '').trim().toLowerCase();
      for (const card of cards) {{
        const haystack = card.dataset.search || '';
        const cardProvider = card.dataset.provider || '';
        const cardStatus = card.dataset.status || '';
        const queryPass = !query || haystack.includes(query);
        const providerPass = !provider || cardProvider === provider;
        const statusPass = !status || cardStatus === status;
        card.hidden = !(queryPass && providerPass && statusPass);
      }}
    }}

    searchInput.addEventListener('input', applyFilters);
    providerFilter.addEventListener('change', applyFilters);
    statusFilter.addEventListener('change', applyFilters);
  </script>
</body>
</html>
"""


def render_export(export_root: Path, markdown_name: str = "HUMAN_READABLE_REPORT.md", html_name: str = "viewer.html") -> tuple[Path, Path]:
    report = _collect_report(export_root)
    markdown_path = export_root / markdown_name
    html_path = export_root / html_name
    markdown_path.write_text(_render_markdown(report, markdown_path), encoding="utf-8")
    html_path.write_text(_render_html(report), encoding="utf-8")
    return markdown_path, html_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a human-readable report and offline viewer for a live audit export bundle.")
    parser.add_argument("export_root", type=Path, help="Path to the audit export root, for example tmp/g4-live-audit-export-20260518")
    parser.add_argument("--markdown-name", default="HUMAN_READABLE_REPORT.md")
    parser.add_argument("--html-name", default="viewer.html")
    args = parser.parse_args()

    export_root = args.export_root.resolve()
    if not export_root.exists():
        raise SystemExit(f"Export root does not exist: {export_root}")
    markdown_path, html_path = render_export(export_root, markdown_name=args.markdown_name, html_name=args.html_name)
    print(json.dumps({
        "exportRoot": str(export_root),
        "markdown": str(markdown_path),
        "html": str(html_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())