from __future__ import annotations

import argparse
import base64
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any

from yggdrasil_sdk.support import load_workspace_dotenv


def _fetch_json(url: str, auth_header: str) -> dict[str, Any]:
    request = urllib.request.Request(url)
    request.add_header("Authorization", auth_header)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _flatten_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _flatten_observation_input(payload: dict[str, Any]) -> str:
    messages = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    chunks: list[str] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")
        chunks.append(f"[{role}] {_flatten_message_content(message.get('content'))}")
    return "\n\n".join(chunks)


def _profile_role(input_text: str) -> str:
    lowered = input_text.lower()
    if "short-window profile represents a constrained" in lowered or "effectivecontextwindow=64000" in lowered:
        return "short64k"
    if "long-window profile represents the wider reference path" in lowered or "effectivecontextwindow=128000" in lowered:
        return "long128k"
    return "unknown"


def _preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        ordered.append(item)
        seen.add(item)
    return ordered


def _extract_snapshot_ids(input_text: str) -> list[str]:
    return _preserve_order(re.findall(r"snapshot (snap_[a-z0-9]+)", input_text, flags=re.IGNORECASE))


def _extract_top_nodes(input_text: str) -> list[str]:
    matches = re.findall(r"Top nodes:\s*([^\.\n]+)", input_text)
    return [match.strip() for match in matches]


def _extract_work_tree_anchor(input_text: str) -> str | None:
    match = re.search(r"Reverse trace anchored at work tree node ([^\.\n]+)", input_text)
    return match.group(1).strip() if match else None


def _extract_equivalence_verdict(output_text: str) -> str:
    section_six = _extract_section_six(output_text)
    conclusion_match = re.search(
        r"(不等价|not equivalent|等价|equivalent)",
        section_six,
        flags=re.IGNORECASE,
    )
    if conclusion_match:
        return conclusion_match.group(1)
    if "不等价" in output_text:
        return "不等价"
    if "等价" in output_text:
        return "等价"
    if "not equivalent" in output_text.lower():
        return "not equivalent"
    if "equivalent" in output_text.lower():
        return "equivalent"
    return "未显式给出"


def _has_final_brief_shape(output_text: str) -> bool:
    required = [
        "任务价值判断",
        "联调覆盖范围",
        "关键集成链路",
        "short-window",
        "long-window",
        "风险与下一步",
    ]
    normalized = output_text.lower()
    return all(fragment.lower() in normalized for fragment in required)


def _window_rows(input_text: str, output_text: str) -> list[dict[str, Any]]:
    snapshot_ids = _extract_snapshot_ids(input_text)
    top_nodes = _extract_top_nodes(input_text)
    anchor = _extract_work_tree_anchor(input_text)
    rows: list[dict[str, Any]] = [
        {
            "window": 1,
            "snapshot": "-",
            "llmAction": "建立真实任务目标与交付约束；尚未出现独立最终交付。",
            "memoryWorkTree": "初始化工作树/记忆检索链路。" + (f" 锚点 {anchor}。" if anchor else ""),
        }
    ]

    final_window = len(snapshot_ids) + 1
    for index, snapshot_id in enumerate(snapshot_ids, start=2):
        top_node_text = top_nodes[min(index - 2, len(top_nodes) - 1)] if top_nodes else "未记录 top nodes"
        llm_action = "无独立模型输出；该窗口主要用于重启后的工作集恢复。"
        if index == final_window:
            llm_action = "模型在该窗口产出最终 Markdown brief，并给出窗口等价判断。"
        rows.append(
            {
                "window": index,
                "snapshot": snapshot_id,
                "llmAction": llm_action,
                "memoryWorkTree": f"恢复快照并重新检索关键节点：{top_node_text}。"
                + (f" 保持 work tree 锚点 {anchor}。" if anchor else ""),
            }
        )
    if len(rows) == 1:
        rows[0]["llmAction"] = "模型直接在首窗口产出最终 Markdown brief。"
    return rows


def _section_excerpt(output_text: str, marker: str, fallback_chars: int = 260) -> str:
    match = re.search(rf"(?is)(?:##+|#+|\*\*)\s*[^\n]*{re.escape(marker)}[^\n]*\n(.*?)(?=\n##+|\n#|\Z)", output_text)
    if match:
        excerpt = re.sub(r"\n{2,}", " ", match.group(1)).strip()
        return excerpt[:fallback_chars]
    compact = re.sub(r"\s+", " ", output_text).strip()
    return compact[:fallback_chars]


def _extract_section_six(output_text: str) -> str:
    patterns = [
        r"(?is)(?:##+|###)\s*6[\.)]?\s*acceptance[^\n]*\n(.*?)(?=\n##+|\n###|\Z)",
        r"(?is)(?:##+|###)\s*6[\.)]?[^\n]*对照结论[^\n]*\n(.*?)(?=\n##+|\n###|\Z)",
        r"(?is)(?:##+|###)\s*6[\.)]?[^\n]*结论[^\n]*\n(.*?)(?=\n##+|\n###|\Z)",
    ]
    for pattern in patterns:
        match = re.search(pattern, output_text)
        if match:
            return match.group(1).strip()
    return output_text


def _build_markdown(trace_id: str, observations: list[dict[str, Any]]) -> str:
    lines = [
        f"# Langfuse 真实任务窗口分析\n",
        f"- traceId: {trace_id}",
        f"- observationCount: {len(observations)}",
        "",
    ]

    for observation in observations:
        output_text = str(observation.get("output") or "")
        input_text = _flatten_observation_input(observation.get("input") or {})
        role = _profile_role(input_text)
        lines.extend(
            [
                f"## {observation.get('model') or 'unknown-model'} / {role}",
                "",
                f"- observationId: {observation.get('id')}",
                f"- finalBriefShape: {'yes' if _has_final_brief_shape(output_text) else 'no'}",
                f"- equivalenceVerdict: {_extract_equivalence_verdict(output_text)}",
                f"- taskResultExcerpt: {_extract_section_six(output_text)[:260]}",
                f"- taskValueExcerpt: {_section_excerpt(output_text, '任务价值判断')}",
                "",
                "### 窗口分析",
                "",
                "| window | snapshot | LLM 在该窗口做了什么 | 记忆树 / 工作树证据 |",
                "|---:|---|---|---|",
            ]
        )
        for row in _window_rows(input_text, output_text):
            lines.append(
                f"| {row['window']} | {row['snapshot']} | {row['llmAction']} | {row['memoryWorkTree']} |"
            )
        lines.extend(
            [
                "",
                "### 最终输出",
                "",
                output_text.strip(),
                "",
            ]
        )

    return "\n".join(lines).strip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze a real-task Langfuse trace and reconstruct final outputs plus window history.")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(".yggdrasil") / "state" / "analysis" / "langfuse-real-task-trace.md",
    )
    args = parser.parse_args()

    load_workspace_dotenv()
    base_url = os.environ["LANGFUSE_BASE_URL"].rstrip("/")
    public_key = os.environ["LANGFUSE_PUBLIC_KEY"]
    secret_key = os.environ["LANGFUSE_SECRET_KEY"]
    auth_value = base64.b64encode(f"{public_key}:{secret_key}".encode("utf-8")).decode("ascii")
    auth_header = f"Basic {auth_value}"

    payload = _fetch_json(f"{base_url}/api/public/observations?traceId={args.trace_id}", auth_header)
    observations = payload.get("data") if isinstance(payload.get("data"), list) else []
    observations.sort(key=lambda item: (str(item.get("model") or ""), str(item.get("id") or "")))

    report = _build_markdown(args.trace_id, observations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()