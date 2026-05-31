from __future__ import annotations
import argparse
import base64
from dataclasses import asdict, dataclass
import hashlib
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from yggdrasil_model_providers.gateway import invoke_model
from .support import load_workspace_dotenv, normalize_excerpt, read_json, resolve_state_dir, resolve_workspace_root
_JSON_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(?P<body>.*?)```", re.IGNORECASE | re.DOTALL)
_REHYDRATED_WINDOW_PATTERN = re.compile(
    r"Rehydrated\s+\d+\s+context\s+items\s+from\s+snapshot\s+snap_[a-z0-9]+",
    re.IGNORECASE,
)
_SNAPSHOT_PATTERN = re.compile(r"snapshot\s+(snap_[a-z0-9]+)", re.IGNORECASE)
_TOP_NODES_PATTERN = re.compile(r"Top nodes:\s*([^\.\n]+)", re.IGNORECASE)
_WORK_TREE_PATTERN = re.compile(r"Reverse trace anchored at work tree node\s+([^\.\n]+)", re.IGNORECASE)
_REHYDRATED_COUNT_PATTERN = re.compile(r"Rehydrated\s+(\d+)\s+context items", re.IGNORECASE)
_RESTORED_FIELDS_PATTERN = re.compile(r"restored\s+(\d+)\s+runtime request fields", re.IGNORECASE)
_RETRIEVED_COUNT_PATTERN = re.compile(r"Retrieved\s+(\d+)\s+nodes\s+for\s+query", re.IGNORECASE)
_MATERIALIZED_COUNT_PATTERN = re.compile(
    r"Materialized\s+(\d+)\s+runtime context items into the memory tree before retrieval",
    re.IGNORECASE,
)
_TASK_GOAL_PATTERN = re.compile(r"(?:Task goal|任务目标):\s*(.+)")
_TASK_OBJECTIVE_PATTERN = re.compile(r"(?:Task objective|任务说明):\s*(.+)")
_PROFILE_HINTS = {
    "short64k": (
        "short-window profile represents a constrained",
        "effectivecontextwindow=64000",
        "g4-web-research-default-grid-storage-short64k",
    ),
    "long24k": (
        "work-tree focused long web-research run",
        "effectivecontextwindow=24000",
        "g4-web-research-work-tree-long-24k",
    ),
}
_SELF_TALK_KEYS = {
    "analysis",
    "reasoning",
    "reasoning_content",
    "reasoningcontent",
    "scratchpad",
    "self_talk",
    "selftalk",
    "thinking",
    "thought",
}
_TOOL_CALL_KEYS = {"toolcalls", "tool_calls"}
_OUTPUT_TAG_PATTERN = re.compile(r"<(?P<name>memory-write)(?P<attrs>\s+[^>]*)?>(?P<body>.*?)</(?P=name)>", re.IGNORECASE | re.DOTALL)
_RUNTIME_SECTION_PATTERN = re.compile(r"<(?P<tag>[a-z_]+)>(?P<body>.*?)</(?P=tag)>", re.IGNORECASE | re.DOTALL)
_CURRENT_OBJECTIVE_PATTERN = re.compile(r"(?:Current objective|当前目标):\s*(.+)", re.IGNORECASE)
_CURRENT_FOCUS_PATTERN = re.compile(r"(?:Current focus|当前焦点):\s*(.+)", re.IGNORECASE)
_RESTART_INSTRUCTION_PATTERN = re.compile(r"Restart instruction:\s*(.+)", re.IGNORECASE)
_MEMORY_HANDOFF_PATTERN = re.compile(r"Memory retrieval handoff:\s*(.+)", re.IGNORECASE)
_PROTECTED_REFS_PATTERN = re.compile(r"Protected refs:\s*(.+)", re.IGNORECASE)
_WORK_TREE_HANDOFF_PATTERN = re.compile(
    r"Work tree handoff:\s*status=(?P<status>[^;\n]+);\s*currentNode=(?P<currentNode>[^;\n]+);\s*recoveryAnchor=(?P<recoveryAnchor>[^\n]+)",
    re.IGNORECASE,
)
_DYNAMIC_ID_PATTERNS = [
    (re.compile(r"snap_[a-z0-9]+", re.IGNORECASE), "snap_*"),
    (re.compile(r"work-tree-node_[a-z0-9]+", re.IGNORECASE), "work-tree-node_*"),
    (re.compile(r"llm_[a-z0-9]+", re.IGNORECASE), "llm_*"),
    (re.compile(r"task_[a-z0-9]+", re.IGNORECASE), "task_*"),
    (re.compile(r"promptcmp_[a-z0-9]+", re.IGNORECASE), "promptcmp_*"),
]
_NULLISH_TEXTS = {"", "null", "none", "{}", "[]"}
class ConversationMessage:
    role: str
    content: str
    source: str
    index: int
class WindowRecord:
    window: int
    snapshot: str
    rawContext: str
    topNodes: list[str]
    workTreeNode: str | None
    rehydratedContextCount: int | None
    restoredFieldCount: int | None
    retrievedNodeCount: int | None
    materializedContextCount: int | None
class LocalInvocationArtifacts:
    requestPath: str | None
    responsePath: str | None
    requestPayload: dict[str, Any]
    responsePayload: dict[str, Any]
class ObservationEvidence:
    observationId: str
    model: str
    profile: str
    invocationId: str | None
    agentRunId: str | None
    taskId: str | None
    taskGoal: str
    taskObjective: str
    messages: list[ConversationMessage]
    initialMessages: list[ConversationMessage]
    windows: list[WindowRecord]
    outputText: str
    inputTools: list[dict[str, Any]]
    metadata: dict[str, Any]
    modelParameters: dict[str, Any]
    usageDetails: dict[str, Any]
    selfTalkFields: list[dict[str, str]]
    assistantProcessUtterances: list[dict[str, Any]]
    toolCallNames: list[str]
    localArtifacts: LocalInvocationArtifacts | None
class LocalDbTraceMatch:
    dbPath: str
    matchedBy: str
    taskId: str
    agentRunId: str | None
    executionRootNodeId: str | None
    nodeWritesByWindow: dict[int, list[dict[str, Any]]]
    restartSnapshotsByWindow: dict[int, list[dict[str, Any]]]
    windowExecutionByWindow: dict[int, list[dict[str, Any]]]
def _fetch_json(url: str, auth_header: str) -> dict[str, Any]:
    request = urllib_request.Request(url)
    request.add_header("Authorization", auth_header)
    with urllib_request.urlopen(request, timeout=60) as response:
        return json.load(response)
def _fetch_observations(trace_id: str, *, base_url: str, auth_header: str) -> dict[str, Any]:
    candidate_queries = [
        urllib_parse.urlencode({"traceId": trace_id, "limit": 200}),
        urllib_parse.urlencode({"traceId": trace_id}),
    ]
    last_error: Exception | None = None
    for query in candidate_queries:
        try:
            return _fetch_json(f"{base_url}/api/public/observations?{query}", auth_header)
        except urllib_error.HTTPError as exc:
            last_error = exc
            if exc.code != 400:
                raise
    if last_error is not None:
        raise last_error
    raise RuntimeError("Failed to fetch Langfuse observations.")
def _normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False)

    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        try:
            decoded = json.loads(stripped)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, str):
            text = decoded

    text = text.replace("\r\n", "\n")
    text = text.replace("\\r\\n", "\n")
    text = text.replace("\\n", "\n")

    if text.count("/n") >= 2:
        text = re.sub(r"(?<![A-Za-z0-9])/n(?=(?:\s|[#>*\-]|\d|[A-Z]|[\u3400-\u9fff]))", "\n", text)

    return text.strip()
def _is_meaningful_text(value: str) -> bool:
    return value.strip().lower() not in _NULLISH_TEXTS
def _flatten_message_content(content: Any) -> str:
    if isinstance(content, str):
        return _normalize_text(content)
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    parts.append(_normalize_text(text))
                    continue
                nested_content = item.get("content")
                if nested_content is not None:
                    nested_text = _flatten_message_content(nested_content)
                    if nested_text:
                        parts.append(nested_text)
                        continue
            nested_text = _normalize_text(item)
            if nested_text:
                parts.append(nested_text)
        return "\n\n".join(part for part in parts if part)
    if isinstance(content, dict):
        for key in ("content", "text", "message", "output", "input"):
            if key in content:
                nested_text = _flatten_message_content(content[key])
                if nested_text:
                    return nested_text
        return _normalize_text(content)
    return _normalize_text(content)
def _flatten_output(value: Any) -> str:
    if isinstance(value, dict) and isinstance(value.get("choices"), list):
        parts: list[str] = []
        for choice in value["choices"]:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if isinstance(message, dict):
                content = _flatten_message_content(message.get("content"))
                if content:
                    parts.append(content)
        if parts:
            return "\n\n".join(parts)
    return _flatten_message_content(value)
def _profile_role(text: str) -> str:
    lowered = text.lower()
    for profile, hints in _PROFILE_HINTS.items():
        if any(hint in lowered for hint in hints):
            return profile
    return "unknown"
def _extract_messages(payload: dict[str, Any]) -> list[ConversationMessage]:
    messages_payload = payload.get("messages") if isinstance(payload.get("messages"), list) else []
    messages: list[ConversationMessage] = []
    for index, message in enumerate(messages_payload, start=1):
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")
        content = _flatten_message_content(message.get("content"))
        messages.append(ConversationMessage(role=role, content=content, source="prompt", index=index))
    return messages
def _input_tools(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tools = payload.get("tools") if isinstance(payload.get("tools"), list) else []
    return [dict(tool) for tool in tools if isinstance(tool, dict)]
def _find_runtime_message(messages: list[ConversationMessage]) -> ConversationMessage | None:
    for message in reversed(messages):
        if message.role != "user":
            continue
        lowered = message.content.lower()
        if "<runtime_state>" in lowered or "system intro: project yggdrasil mounts identity" in lowered:
            return message
    return None
def _split_window_contexts(runtime_message: str) -> list[str]:
    normalized = _normalize_text(runtime_message)
    if not normalized:
        return []

    matches = list(_REHYDRATED_WINDOW_PATTERN.finditer(normalized))
    if not matches:
        return [normalized]

    chunks: list[str] = []
    initial_chunk = normalized[: matches[0].start()].strip()
    if initial_chunk:
        chunks.append(initial_chunk)

    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(normalized)
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
    return chunks
def _extract_first_int(pattern: re.Pattern[str], text: str) -> int | None:
    match = pattern.search(text)
    if match is None:
        return None
    return int(match.group(1))
def _split_top_nodes(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]
def _build_window_records(runtime_message: str) -> list[WindowRecord]:
    chunks = _split_window_contexts(runtime_message)
    windows: list[WindowRecord] = []
    for index, chunk in enumerate(chunks, start=1):
        snapshot_match = _SNAPSHOT_PATTERN.search(chunk)
        top_nodes_match = _TOP_NODES_PATTERN.search(chunk)
        work_tree_match = _WORK_TREE_PATTERN.search(chunk)
        windows.append(
            WindowRecord(
                window=index,
                snapshot=snapshot_match.group(1) if snapshot_match else "-",
                rawContext=chunk,
                topNodes=_split_top_nodes(top_nodes_match.group(1) if top_nodes_match else None),
                workTreeNode=work_tree_match.group(1).strip() if work_tree_match else None,
                rehydratedContextCount=_extract_first_int(_REHYDRATED_COUNT_PATTERN, chunk),
                restoredFieldCount=_extract_first_int(_RESTORED_FIELDS_PATTERN, chunk),
                retrievedNodeCount=_extract_first_int(_RETRIEVED_COUNT_PATTERN, chunk),
                materializedContextCount=_extract_first_int(_MATERIALIZED_COUNT_PATTERN, chunk),
            )
        )
    return windows
def _extract_task_field(pattern: re.Pattern[str], text: str) -> str:
    match = pattern.search(text)
    if match is None:
        return "未显式记录"
    return _normalize_text(match.group(1))
def _append_unique(items: list[str], value: str) -> None:
    if not value or value in items:
        return
    items.append(value)
def _extract_tool_call_names(value: Any, accumulator: list[str]) -> None:
    if isinstance(value, dict):
        lowered_keys = {str(key).lower(): key for key in value}
        if "function" in lowered_keys:
            function_payload = value[lowered_keys["function"]]
            if isinstance(function_payload, dict):
                name = function_payload.get("name")
                if isinstance(name, str):
                    _append_unique(accumulator, name)
        if "name" in lowered_keys and len(value) == 1:
            name = value[lowered_keys["name"]]
            if isinstance(name, str):
                _append_unique(accumulator, name)
        for nested in value.values():
            _extract_tool_call_names(nested, accumulator)
        return
    if isinstance(value, list):
        for item in value:
            _extract_tool_call_names(item, accumulator)
def _collect_self_talk_and_tools(payload: Any) -> tuple[list[dict[str, str]], list[str]]:
    self_talk_fields: list[dict[str, str]] = []
    tool_call_names: list[str] = []

    def _walk(node: Any, path: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                key_text = str(key)
                key_lower = key_text.lower()
                child_path = f"{path}.{key_text}" if path else key_text
                if key_lower in _SELF_TALK_KEYS:
                    normalized_value = _flatten_message_content(value)
                    if normalized_value and _is_meaningful_text(normalized_value):
                        self_talk_fields.append({"path": child_path, "value": normalized_value})
                if key_lower in _TOOL_CALL_KEYS:
                    _extract_tool_call_names(value, tool_call_names)
                _walk(value, child_path)
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                child_path = f"{path}[{index}]"
                _walk(item, child_path)

    _walk(payload, "observation")
    return self_talk_fields, tool_call_names
def _local_artifact_candidates(workspace_root: Path, invocation_id: str) -> list[tuple[Path, Path]]:
    state_dir = resolve_state_dir(workspace_root)
    candidates = [
        (
            state_dir / "llm" / "requests" / f"{invocation_id}.json",
            state_dir / "llm" / "responses" / f"{invocation_id}.json",
        )
    ]
    sandboxes_root = state_dir / "evaluation-sandboxes"
    if sandboxes_root.exists():
        for sandbox in sandboxes_root.iterdir():
            if not sandbox.is_dir():
                continue
            sandbox_state = sandbox / ".yggdrasil" / "state" / "llm"
            candidates.append(
                (
                    sandbox_state / "requests" / f"{invocation_id}.json",
                    sandbox_state / "responses" / f"{invocation_id}.json",
                )
            )
    return candidates
def _load_local_invocation_artifacts(invocation_id: str | None, workspace_root: Path | None) -> LocalInvocationArtifacts | None:
    if not invocation_id or workspace_root is None:
        return None
    for request_path, response_path in _local_artifact_candidates(workspace_root, invocation_id):
        if not request_path.exists() and not response_path.exists():
            continue
        request_payload = read_json(request_path, {}) if request_path.exists() else {}
        response_payload = read_json(response_path, {}) if response_path.exists() else {}
        return LocalInvocationArtifacts(
            requestPath=str(request_path) if request_path.exists() else None,
            responsePath=str(response_path) if response_path.exists() else None,
            requestPayload=request_payload if isinstance(request_payload, dict) else {},
            responsePayload=response_payload if isinstance(response_payload, dict) else {},
        )
    return None
def _assistant_process_utterances(messages: list[ConversationMessage], runtime_message_index: int | None) -> list[dict[str, Any]]:
    utterances: list[dict[str, Any]] = []
    for message in messages:
        if message.role != "assistant":
            continue
        if runtime_message_index is not None and message.index >= runtime_message_index:
            continue
        if not message.content:
            continue
        utterances.append(
            {
                "index": message.index,
                "role": message.role,
                "content": message.content,
            }
        )
    return utterances
def _build_observation_evidence(observation: dict[str, Any], workspace_root: Path | None = None) -> ObservationEvidence:
    input_payload = observation.get("input") if isinstance(observation.get("input"), dict) else {}
    messages = _extract_messages(input_payload)
    runtime_message = _find_runtime_message(messages)
    runtime_index = runtime_message.index if runtime_message is not None else None
    runtime_text = runtime_message.content if runtime_message is not None else "\n\n".join(message.content for message in messages)
    windows = _build_window_records(runtime_text)
    task_goal = _extract_task_field(_TASK_GOAL_PATTERN, runtime_text)
    task_objective = _extract_task_field(_TASK_OBJECTIVE_PATTERN, runtime_text)
    self_talk_fields, tool_call_names = _collect_self_talk_and_tools(observation)
    output_text = _flatten_output(observation.get("output"))
    initial_messages = [message for message in messages if runtime_index is None or message.index < runtime_index]
    invocation_id = str(input_payload.get("invocationId") or "").strip() or None
    agent_run_id = str(input_payload.get("agentRunId") or "").strip() or None
    task_id = str(input_payload.get("taskId") or "").strip() or None
    local_artifacts = _load_local_invocation_artifacts(invocation_id, workspace_root)

    return ObservationEvidence(
        observationId=str(observation.get("id") or "unknown-observation"),
        model=str(observation.get("model") or "unknown-model"),
        profile=_profile_role(runtime_text),
        invocationId=invocation_id,
        agentRunId=agent_run_id,
        taskId=task_id,
        taskGoal=task_goal,
        taskObjective=task_objective,
        messages=messages,
        initialMessages=initial_messages,
        windows=windows,
        outputText=output_text,
        inputTools=_input_tools(input_payload),
        metadata=observation.get("metadata") if isinstance(observation.get("metadata"), dict) else {},
        modelParameters=observation.get("modelParameters") if isinstance(observation.get("modelParameters"), dict) else {},
        usageDetails=observation.get("usageDetails") if isinstance(observation.get("usageDetails"), dict) else {},
        selfTalkFields=self_talk_fields,
        assistantProcessUtterances=_assistant_process_utterances(messages, runtime_index),
        toolCallNames=tool_call_names,
        localArtifacts=local_artifacts,
    )
def _has_required_sections(output_text: str) -> bool:
    required_fragments = [
        "任务价值判断",
        "联调覆盖范围",
        "关键集成链路",
        "short-window",
        "long-window",
        "acceptance 对照结论",
        "风险与下一步",
    ]
    lowered = output_text.lower()
    return all(fragment.lower() in lowered for fragment in required_fragments)
def _fallback_summary(window: WindowRecord, total_windows: int) -> str:
    if window.window == 1:
        top_nodes = "、".join(window.topNodes[:3]) or "初始任务约束"
        return f"建立任务目标与输出合同，并挂载首批证据：{top_nodes}。"
    if window.window == total_windows:
        top_nodes = "、".join(window.topNodes[:3]) or "最终交付合同"
        return f"在最终窗口整合恢复态上下文，基于 {top_nodes} 产出最终交付。"
    top_nodes = "、".join(window.topNodes[:3]) or "恢复态最小证据集"
    return f"恢复快照 {window.snapshot} 并继续围绕 {top_nodes} 推进任务主线。"
def _fallback_steps(window: WindowRecord, total_windows: int) -> list[str]:
    if window.window == 1:
        steps = [
            "首先读取系统角色、用户任务和输出合同。",
            "然后固定当前目标、焦点和需要覆盖的证据面。",
        ]
        if window.materializedContextCount is not None:
            steps.append(f"接着物化 {window.materializedContextCount} 个运行时上下文项到记忆树。")
        if window.topNodes:
            steps.append(f"最后围绕 {'、'.join(window.topNodes[:3])} 建立首轮工作集。")
        return steps

    steps = []
    if window.rehydratedContextCount is not None:
        steps.append(f"首先从快照 {window.snapshot} 恢复 {window.rehydratedContextCount} 个上下文项。")
    if window.restoredFieldCount is not None:
        steps.append(f"然后恢复 {window.restoredFieldCount} 个运行时请求字段。")
    if window.retrievedNodeCount is not None:
        node_summary = "、".join(window.topNodes[:3]) or "最小证据集"
        steps.append(f"接着检索 {window.retrievedNodeCount} 个节点，继续围绕 {node_summary} 工作。")
    if window.workTreeNode:
        steps.append(f"保持工作树锚点 {window.workTreeNode}，避免任务主线漂移。")
    if window.window == total_windows:
        steps.append("最后基于恢复态上下文直接产出最终结果。")
    return steps or ["该窗口缺少足够的结构化证据，无法进一步细分步骤。"]
def _fallback_reason_text(reason_code: str) -> str:
    if reason_code == "analysis-json-truncated":
        return "分析模型已被成功调用，但结构化 JSON 输出在返回阶段被截断，已退回到基于窗口证据和最终输出的启发式判断。"
    if reason_code == "analysis-json-invalid":
        return "分析模型已被成功调用，但结构化 JSON 输出不合法，已退回到基于窗口证据和最终输出的启发式判断。"
    if reason_code == "analysis-llm-fallback":
        return "分析模型调用走了 fallback，已退回到基于窗口证据和最终输出的启发式判断。"
    return "分析阶段未能得到可解析的结构化结果，已退回到基于窗口证据和最终输出的启发式判断。"
def _fallback_layer_analysis(evidence: ObservationEvidence, reason_code: str) -> dict[str, Any]:
    output_text = evidence.outputText
    windows = evidence.windows or [
        WindowRecord(
            window=1,
            snapshot="-",
            rawContext="",
            topNodes=[],
            workTreeNode=None,
            rehydratedContextCount=None,
            restoredFieldCount=None,
            retrievedNodeCount=None,
            materializedContextCount=None,
        )
    ]
    completion = "completed" if output_text and _has_required_sections(output_text) else "partial"
    effectiveness = "good" if completion == "completed" else "mixed"
    result_excerpt = normalize_excerpt(output_text or "未提取到最终输出", 240)
    return {
        "layer1": {
            "task_goal": evidence.taskGoal,
            "task_result": result_excerpt,
            "completion_judgement": completion,
            "agent_effectiveness": effectiveness,
            "reason": _fallback_reason_text(reason_code),
        },
        "layer2": [
            {
                "window": window.window,
                "snapshot": window.snapshot,
                "one_sentence": _fallback_summary(window, len(windows)),
            }
            for window in windows
        ],
        "layer3": [
            {
                "window": window.window,
                "snapshot": window.snapshot,
                "steps": _fallback_steps(window, len(windows)),
            }
            for window in windows
        ],
    }
def _analysis_prompt_payload(evidence: ObservationEvidence) -> dict[str, Any]:
    return {
        "observationId": evidence.observationId,
        "model": evidence.model,
        "profile": evidence.profile,
        "invocationId": evidence.invocationId,
        "agentRunId": evidence.agentRunId,
        "taskId": evidence.taskId,
        "taskGoal": evidence.taskGoal,
        "taskObjective": evidence.taskObjective,
        "windows": [asdict(window) for window in evidence.windows],
        "initialMessages": [asdict(message) for message in evidence.initialMessages],
        "assistantProcessUtterances": evidence.assistantProcessUtterances,
        "selfTalkFields": evidence.selfTalkFields,
        "toolCallNames": evidence.toolCallNames,
        "inputTools": evidence.inputTools,
        "modelParameters": evidence.modelParameters,
        "metadata": evidence.metadata,
        "usageDetails": evidence.usageDetails,
        "finalOutput": evidence.outputText,
    }
def _build_analysis_messages(evidence: ObservationEvidence) -> list[dict[str, str]]:
    system_prompt = (
        "你是一个严格基于证据的真实任务窗口分析器。"
        "你会基于提供的窗口原始上下文、初始对话、最终输出和自言自语字段，"
        "生成 3 个层次的结构化分析。不要虚构窗口内没有发生的动作。"
        "如果多个中间窗口高度相似，你必须指出它们相同的地方，以及仍然存在的具体差异"
        "（例如 snapshot、topNodes、workTreeNode、delivery contract、resume 指令变化）。"
        "除 completion_judgement 和 agent_effectiveness 这两个枚举值外，所有字符串都必须使用简体中文，"
        "不要直接复制英文任务目标，要把英文合同翻译成中文摘要。"
        "输出必须是 JSON，对象仅允许包含 layer1、layer2、layer3 三个顶级键。"
    )
    user_prompt = {
        "instructions": {
            "language": "zh-CN",
            "layer1": {
                "task_goal": "基于证据给出中文任务目标摘要。",
                "task_result": "基于最终输出给出中文任务结果摘要。",
                "completion_judgement": "只能是 completed / partial / failed / unknown。",
                "agent_effectiveness": "只能是 excellent / good / mixed / poor / unknown。",
                "reason": "用中文简要说明判断依据。",
            },
            "layer2": "对每个窗口给出一句中文总结，必须与输入 windows 的数量一致。字段名用 window、snapshot、one_sentence。",
            "layer3": "对每个窗口给出中文过程步骤，必须与输入 windows 的数量一致。字段名用 window、snapshot、steps；steps 是字符串数组，使用‘首先/然后/接着/最后’这类顺序表达，但不要为了凑格式而编造动作。",
            "grounding": [
                "优先使用 windows.rawContext 和 finalOutput。",
                "只有 initialMessages 或 assistantProcessUtterances 里出现的助手话语，才能被视为自言自语过程。",
                "如果窗口只有恢复态证据，就明确写成恢复、检索、锚定、继续推进，不要写成已经完成了新的工程实现。",
                "即使原始任务合同或最终输出包含英文，你也必须把叙述性字段写成中文。",
            ],
        },
        "evidence": _analysis_prompt_payload(evidence),
    }
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False, indent=2)},
    ]
def _strip_json_wrappers(text: str) -> str:
    stripped = text.strip()
    fenced_match = _JSON_FENCE_PATTERN.search(stripped)
    if fenced_match is not None:
        stripped = fenced_match.group("body").strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        return stripped[start : end + 1]
    return stripped
def _analysis_token_budget(evidence: ObservationEvidence, *, retry: bool = False) -> int:
    window_count = max(len(evidence.windows), 1)
    budget = 1400 + window_count * 520
    if retry:
        budget = int(budget * 1.5)
    return max(3200, min(budget, 14000))
def _json_failure_reason(error: json.JSONDecodeError, candidate: str) -> str:
    if error.pos >= max(len(candidate) - 8, 0):
        return "analysis-json-truncated"
    return "analysis-json-invalid"
def _run_llm_layer_analysis(
    *,
    evidence: ObservationEvidence,
    requested_provider: str,
    requested_model: str,
    workspace_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    parse_status = "ok"
    result: dict[str, Any] | None = None
    messages = _build_analysis_messages(evidence)
    for retry in (False, True):
        result = invoke_model(
            requested_model=requested_model,
            requested_provider=requested_provider,
            messages=messages,
            temperature=0.1,
            max_tokens=_analysis_token_budget(evidence, retry=retry),
            workspace_root=workspace_root,
            allow_fallback=True,
        )
        output_text = _flatten_output(result.get("outputText") or result)
        candidate = _strip_json_wrappers(output_text)
        try:
            parsed = json.loads(candidate)
            return parsed, result, parse_status
        except json.JSONDecodeError as exc:
            if str(result.get("mode") or "") != "live":
                parse_status = "analysis-llm-fallback"
                break
            parse_status = _json_failure_reason(exc, candidate)
            if parse_status != "analysis-json-truncated" or retry:
                break
    assert result is not None
    return _fallback_layer_analysis(evidence, parse_status), result, parse_status
def _tool_names_from_local_artifacts(artifacts: LocalInvocationArtifacts | None) -> list[str]:
    if artifacts is None:
        return []
    tool_names: list[str] = []
    for execution in artifacts.responsePayload.get("toolExecutions") or []:
        if not isinstance(execution, dict):
            continue
        tool = execution.get("tool") if isinstance(execution.get("tool"), dict) else {}
        name = tool.get("name")
        if isinstance(name, str):
            _append_unique(tool_names, name)
    for summary in artifacts.responsePayload.get("toolExecutionSummaries") or []:
        if not isinstance(summary, dict):
            continue
        name = summary.get("tool")
        if isinstance(name, str):
            _append_unique(tool_names, name)
    for round_summary in artifacts.responsePayload.get("rounds") or []:
        if not isinstance(round_summary, dict):
            continue
        for tool_name in round_summary.get("toolCalls") or []:
            if isinstance(tool_name, str):
                _append_unique(tool_names, tool_name)
    return tool_names
def _self_talk_from_local_artifacts(artifacts: LocalInvocationArtifacts | None) -> list[dict[str, str]]:
    if artifacts is None:
        return []
    fields: list[dict[str, str]] = []
    request_payload = artifacts.requestPayload
    response_payload = artifacts.responsePayload
    raw_response = response_payload.get("rawResponse") if isinstance(response_payload.get("rawResponse"), dict) else {}
    for key in ("reasoningContent", "reasoning_content"):
        value = raw_response.get(key)
        if isinstance(value, str) and _is_meaningful_text(value):
            fields.append({"path": f"localArtifacts.responsePayload.rawResponse.{key}", "value": value})
    rounds = response_payload.get("rounds") if isinstance(response_payload.get("rounds"), list) else []
    for index, round_summary in enumerate(rounds, start=1):
        if not isinstance(round_summary, dict):
            continue
        if bool(round_summary.get("reasoningContentPresent")):
            fields.append(
                {
                    "path": f"localArtifacts.responsePayload.rounds[{index - 1}].reasoningContentPresent",
                    "value": "true",
                }
            )
    final_message_digests = request_payload.get("finalMessageDigests") if isinstance(request_payload.get("finalMessageDigests"), list) else []
    for index, digest in enumerate(final_message_digests):
        if not isinstance(digest, dict):
            continue
        preview = digest.get("reasoningContentPreview")
        if isinstance(preview, str) and _is_meaningful_text(preview):
            fields.append(
                {
                    "path": f"localArtifacts.requestPayload.finalMessageDigests[{index}].reasoningContentPreview",
                    "value": preview,
                }
            )
    return fields
def _extract_output_tags(output_text: str) -> list[dict[str, str]]:
    tags: list[dict[str, str]] = []
    for match in _OUTPUT_TAG_PATTERN.finditer(output_text):
        body = _normalize_text(match.group("body"))
        if not body:
            continue
        tags.append({"path": f"assistantFinalOutput.{match.group('name')}", "value": body})
    return tags
def _build_layer4_windows(evidence: ObservationEvidence) -> list[dict[str, Any]]:
    windows = evidence.windows or [
        WindowRecord(
            window=1,
            snapshot="-",
            rawContext="",
            topNodes=[],
            workTreeNode=None,
            rehydratedContextCount=None,
            restoredFieldCount=None,
            retrievedNodeCount=None,
            materializedContextCount=None,
        )
    ]
    final_window_index = len(windows)
    local_self_talk = _self_talk_from_local_artifacts(evidence.localArtifacts)
    local_tool_names = _tool_names_from_local_artifacts(evidence.localArtifacts)
    output_tags = _extract_output_tags(evidence.outputText)
    layer4: list[dict[str, Any]] = []
    for window in windows:
        structured_self_talk: list[dict[str, str]] = []
        assistant_utterances: list[dict[str, Any]] = []
        tool_names: list[str] = []
        sources: list[str] = []
        notes: list[str] = []

        if window.window == 1 and evidence.assistantProcessUtterances:
            assistant_utterances.extend(evidence.assistantProcessUtterances)
            sources.append("initialPromptMessages")
        if window.window == final_window_index:
            structured_self_talk.extend(evidence.selfTalkFields)
            structured_self_talk.extend(local_self_talk)
            structured_self_talk.extend(output_tags)
            for tool_name in evidence.toolCallNames:
                _append_unique(tool_names, tool_name)
            for tool_name in local_tool_names:
                _append_unique(tool_names, tool_name)
            if evidence.selfTalkFields:
                sources.append("langfuseObservationFields")
            if local_self_talk or local_tool_names:
                sources.append("localInvocationArtifacts")
            if output_tags:
                sources.append("assistantFinalOutput")

        if not structured_self_talk and not assistant_utterances and not tool_names:
            notes.append("Langfuse 当前 observation 未记录该窗口的独立 assistant 自言自语字段或工具调用。")
        if evidence.localArtifacts is None and window.window == final_window_index:
            notes.append("未在当前工作区找到对应 invocation 的本地 request/response 工件，因此无法补回 conversationMessages、toolExecutions、rawResponse 等本地审计信息。")

        layer4.append(
            {
                "window": window.window,
                "snapshot": window.snapshot,
                "structuredSelfTalkFields": structured_self_talk,
                "assistantProcessUtterances": assistant_utterances,
                "toolCallNames": tool_names,
                "sources": sources,
                "notes": notes,
            }
        )
    return layer4
def _structured_window_state(window: WindowRecord) -> dict[str, Any]:
    return {
        "window": window.window,
        "snapshot": window.snapshot,
        "topNodes": window.topNodes,
        "workTreeNode": window.workTreeNode,
        "rehydratedContextCount": window.rehydratedContextCount,
        "restoredFieldCount": window.restoredFieldCount,
        "retrievedNodeCount": window.retrievedNodeCount,
        "materializedContextCount": window.materializedContextCount,
    }
def _split_runtime_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []
    for match in _RUNTIME_SECTION_PATTERN.finditer(text):
        body = _normalize_text(match.group("body"))
        if not body:
            continue
        sections.append(
            {
                "role": f"runtime_section_{match.group('tag').lower()}",
                "content": body,
                "source": "runtime_state_section",
            }
        )
    return sections
def _build_full_conversation(evidence: ObservationEvidence) -> list[dict[str, Any]]:
    windows = evidence.windows
    if not windows:
        messages = [asdict(message) for message in evidence.messages]
        if evidence.outputText:
            messages.append({"role": "assistant_final_output", "content": evidence.outputText, "source": "output"})
        return [{"window": 1, "snapshot": "-", "messages": messages}]

    transcript: list[dict[str, Any]] = []
    for window in windows:
        messages: list[dict[str, Any]] = []
        if window.window == 1:
            messages.extend(asdict(message) for message in evidence.initialMessages)
            if evidence.inputTools:
                messages.append(
                    {
                        "role": "langfuse_input_tools",
                        "content": json.dumps(evidence.inputTools, ensure_ascii=False, indent=2),
                        "source": "langfuse.input.tools",
                    }
                )
        if window.rawContext:
            messages.append(
                {
                    "role": "runtime_window_context",
                    "content": window.rawContext,
                    "source": "runtime_state",
                }
            )
            messages.append(
                {
                    "role": "runtime_window_structured_state",
                    "content": json.dumps(_structured_window_state(window), ensure_ascii=False, indent=2),
                    "source": "analysis.reconstructed_window_state",
                }
            )
            messages.extend(_split_runtime_sections(window.rawContext))
        if window.window == len(windows):
            if evidence.metadata:
                messages.append(
                    {
                        "role": "langfuse_observation_metadata",
                        "content": json.dumps(evidence.metadata, ensure_ascii=False, indent=2),
                        "source": "langfuse.metadata",
                    }
                )
            if evidence.modelParameters:
                messages.append(
                    {
                        "role": "langfuse_model_parameters",
                        "content": json.dumps(evidence.modelParameters, ensure_ascii=False, indent=2),
                        "source": "langfuse.modelParameters",
                    }
                )
            if evidence.usageDetails:
                messages.append(
                    {
                        "role": "langfuse_usage_details",
                        "content": json.dumps(evidence.usageDetails, ensure_ascii=False, indent=2),
                        "source": "langfuse.usageDetails",
                    }
                )
            if evidence.localArtifacts is not None:
                if evidence.localArtifacts.requestPath is not None:
                    messages.append(
                        {
                            "role": "local_invocation_request_artifact",
                            "content": json.dumps(evidence.localArtifacts.requestPayload, ensure_ascii=False, indent=2),
                            "source": evidence.localArtifacts.requestPath,
                        }
                    )
                if evidence.localArtifacts.responsePath is not None:
                    messages.append(
                        {
                            "role": "local_invocation_response_artifact",
                            "content": json.dumps(evidence.localArtifacts.responsePayload, ensure_ascii=False, indent=2),
                            "source": evidence.localArtifacts.responsePath,
                        }
                    )
        if window.window == len(windows) and evidence.outputText:
            messages.append(
                {
                    "role": "assistant_final_output",
                    "content": evidence.outputText,
                    "source": "observation.output",
                }
            )
        transcript.append(
            {
                "window": window.window,
                "snapshot": window.snapshot,
                "messages": messages,
            }
        )
    return transcript
