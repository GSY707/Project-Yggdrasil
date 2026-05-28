from __future__ import annotations

from pathlib import Path

from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_execution_audit_markdown
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_execution_audit_payload
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_observation_evidence
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_observation_execution_audit
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_full_conversation
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_layer4_windows
from yggdrasil_sdk.langfuse_trace_layered_analysis import _build_window_execution_audits
from yggdrasil_sdk.langfuse_trace_layered_analysis import LocalDbTraceMatch
from yggdrasil_sdk.langfuse_trace_layered_analysis import _normalize_text
from yggdrasil_sdk.langfuse_trace_layered_analysis import _split_window_contexts


def test_normalize_text_unescapes_newlines() -> None:
    raw = "第一行\\n第二行/n- 列表一/n- 列表二"

    normalized = _normalize_text(raw)

    assert normalized == "第一行\n第二行\n- 列表一\n- 列表二"


def test_split_window_contexts_preserves_initial_and_rehydrated_windows() -> None:
    runtime_message = (
        "System intro: Project Yggdrasil mounts identity. "
        "Top nodes: live stress evidence, evaluation/suites/g4-real-task-web-research-default.json, window policy. "
        "Reverse trace anchored at work tree node work-tree-node_initial. "
        "Rehydrated 1 context items from snapshot snap_abc123 and restored 25 runtime request fields. "
        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy, docs/DEVELOPER_GUIDE.md. "
        "Reverse trace anchored at work tree node work-tree-node_mid. "
        "Rehydrated 1 context items from snapshot snap_def456 and restored 25 runtime request fields. "
        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, delivery mode contract, window policy. "
        "Reverse trace anchored at work tree node work-tree-node_final. "
        "Task goal: Produce the final release brief."
    )

    windows = _split_window_contexts(runtime_message)

    assert len(windows) == 3
    assert windows[0].startswith("System intro")
    assert windows[1].startswith("Rehydrated 1 context items from snapshot snap_abc123")
    assert windows[2].startswith("Rehydrated 1 context items from snapshot snap_def456")


def test_build_observation_evidence_reconstructs_window_transcript() -> None:
    observation = {
        "id": "obs_demo",
        "model": "LongCat-2.0-Preview",
        "metadata": {"trace": "demo"},
        "modelParameters": {"temperature": 0.1},
        "usageDetails": {"input": 12, "output": 34},
        "input": {
            "tools": [{"name": "read_file", "description": "read a file"}],
            "messages": [
                {"role": "system", "content": "系统提示"},
                {"role": "user", "content": "用户任务"},
                {"role": "assistant", "content": "先固定范围，再交付。"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "System intro: Project Yggdrasil mounts identity. "
                        "Materialized 2192 runtime context items into the memory tree before retrieval. "
                        "Top nodes: live stress evidence, evaluation/suites/g4-real-task-web-research-default.json, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_1. "
                        "Rehydrated 1 context items from snapshot snap_mid and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy, docs/DEVELOPER_GUIDE.md. "
                        "Reverse trace anchored at work tree node work-tree-node_2. "
                        "Task goal: Produce the final release brief.\n"
                        "Task objective: Deliver the final result.\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "## 1. 任务价值判断\\n最终交付完成",
    }

    evidence = _build_observation_evidence(observation)
    layer4 = _build_layer4_windows(evidence)
    conversation = _build_full_conversation(evidence)

    assert evidence.taskGoal == "Produce the final release brief."
    assert evidence.taskObjective == "Deliver the final result."
    assert len(evidence.windows) == 2
    assert evidence.windows[1].snapshot == "snap_mid"
    assert [item["window"] for item in layer4] == [1, 2]
    assert layer4[0]["assistantProcessUtterances"][0]["content"] == "先固定范围，再交付。"
    assert "Langfuse 当前 observation 未记录该窗口的独立 assistant 自言自语字段或工具调用。" in layer4[1]["notes"]
    assert any("未在当前工作区找到对应 invocation" in note for note in layer4[1]["notes"])
    assert conversation[0]["messages"][0]["role"] == "system"
    assert any(message["role"] == "langfuse_input_tools" for message in conversation[0]["messages"])
    assert any(message["role"] == "runtime_window_context" for message in conversation[1]["messages"])
    assert any(message["role"] == "runtime_window_structured_state" for message in conversation[1]["messages"])
    assert any(message["role"] == "langfuse_observation_metadata" for message in conversation[1]["messages"])
    assert conversation[1]["messages"][-1]["role"] == "assistant_final_output"
    assert conversation[1]["messages"][-1]["content"].startswith("## 1. 任务价值判断")


def test_build_observation_evidence_supports_chinese_runtime_labels() -> None:
    observation = {
        "id": "obs_demo_zh",
        "model": "LongCat-2.0-Preview",
        "input": {
            "messages": [
                {"role": "system", "content": "系统提示"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "任务目标: 产出最终发布摘要。\n"
                        "任务说明: 直接给出最终结果。\n"
                        "当前目标: 对齐交付合同。\n"
                        "当前焦点: 汇总证据并收敛结论。\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "最终交付完成",
    }

    evidence = _build_observation_evidence(observation)

    assert evidence.taskGoal == "产出最终发布摘要。"
    assert evidence.taskObjective == "直接给出最终结果。"


def test_window_execution_audit_marks_repeated_middle_windows() -> None:
    observation = {
        "id": "obs_repeat",
        "model": "LongCat-2.0-Preview",
        "metadata": {"traceId": "trace_repeat", "toolExecutionCount": 0},
        "input": {
            "messages": [
                {"role": "system", "content": "系统提示"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "System intro: Project Yggdrasil mounts identity. "
                        "Top nodes: baseline evidence, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_initial. "
                        "Rehydrated 1 context items from snapshot snap_a and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: parity-analysis. "
                        "Restart instruction: Continue from carry-forward package. "
                        "Rehydrated 1 context items from snapshot snap_b and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: parity-analysis. "
                        "Restart instruction: Continue from carry-forward package. "
                        "Rehydrated 1 context items from snapshot snap_c and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, final delivery contract. "
                        "Reverse trace anchored at work tree node work-tree-node_final. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: final-delivery. "
                        "Restart instruction: Produce the final report now. "
                        "Task goal: Produce the final release brief.\n"
                        "Task objective: Deliver the final result.\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "最终交付完成",
    }

    evidence = _build_observation_evidence(observation)
    window_audits = _build_window_execution_audits(evidence, None)
    observation_audit = _build_observation_execution_audit(
        trace_id="trace_repeat",
        evidence=evidence,
        workspace_root=Path("."),
    )

    assert [item["window"] for item in window_audits] == [1, 2, 3, 4]
    assert window_audits[1]["classification"] == "cluster-anchor-window"
    assert window_audits[2]["classification"] == "repeated-carry-forward-window"
    assert window_audits[2]["discardCandidate"] is True
    assert window_audits[3]["classification"] == "delivery-window"
    assert observation_audit["discardWindows"] == [3]


def test_window_execution_audit_uses_runtime_window_records_when_available() -> None:
    observation = {
        "id": "obs_runtime_records",
        "model": "LongCat-2.0-Preview",
        "metadata": {"traceId": "trace_runtime_records", "toolExecutionCount": 0},
        "input": {
            "taskId": "task_runtime_records",
            "agentRunId": "run_runtime_records_final",
            "messages": [
                {"role": "system", "content": "系统提示"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "System intro: Project Yggdrasil mounts identity. "
                        "Top nodes: baseline evidence, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_initial. "
                        "Rehydrated 1 context items from snapshot snap_a and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: parity-analysis. "
                        "Restart instruction: Continue from carry-forward package. "
                        "Rehydrated 1 context items from snapshot snap_b and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: parity-analysis. "
                        "Restart instruction: Continue from carry-forward package. "
                        "Rehydrated 1 context items from snapshot snap_c and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, final delivery contract. "
                        "Reverse trace anchored at work tree node work-tree-node_final. "
                        "Current objective: Deliver parity brief. "
                        "Current focus: final-delivery. "
                        "Restart instruction: Produce the final report now. "
                        "Task goal: Produce the final release brief.\n"
                        "Task objective: Deliver the final result.\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "最终交付完成",
    }

    evidence = _build_observation_evidence(observation)
    local_db_match = LocalDbTraceMatch(
        dbPath="",
        matchedBy="window-execution-artifact",
        taskId="task_runtime_records",
        agentRunId="run_runtime_records_final",
        executionRootNodeId=None,
        nodeWritesByWindow={},
        restartSnapshotsByWindow={},
        windowExecutionByWindow={
            2: [
                {
                    "taskId": "task_runtime_records",
                    "windowIndex": 2,
                    "transitionOutcome": "restart-requested",
                    "currentObjective": "Deliver parity brief.",
                    "currentFocus": "parity-analysis.",
                    "responseRequirementsDigest": "req_same",
                    "restartMessageDigest": "restart_same",
                    "protectedRefIds": ["node_a"],
                    "workTreeCurrentNodeId": "work-tree-node_repeat",
                    "workTreeStatus": "planned",
                    "workTreeRecoveryAnchor": "resume:repeat",
                    "stateFingerprint": "state_repeat",
                    "memoryRetrievalState": {
                        "matchedNodeCount": 4,
                        "materializedNodeCount": 1,
                        "summary": "retrieval same",
                        "retrievalFingerprint": "retr_repeat",
                    },
                    "llm": {"planningStub0_1": 1},
                }
            ],
            3: [
                {
                    "taskId": "task_runtime_records",
                    "windowIndex": 3,
                    "transitionOutcome": "restart-requested",
                    "currentObjective": "Deliver parity brief.",
                    "currentFocus": "parity-analysis.",
                    "responseRequirementsDigest": "req_same",
                    "restartMessageDigest": "restart_same",
                    "protectedRefIds": ["node_a"],
                    "workTreeCurrentNodeId": "work-tree-node_repeat",
                    "workTreeStatus": "planned",
                    "workTreeRecoveryAnchor": "resume:repeat",
                    "stateFingerprint": "state_repeat",
                    "memoryRetrievalState": {
                        "matchedNodeCount": 4,
                        "materializedNodeCount": 1,
                        "summary": "retrieval same",
                        "retrievalFingerprint": "retr_repeat",
                    },
                    "llm": {"planningStub0_1": 1},
                }
            ],
            4: [
                {
                    "taskId": "task_runtime_records",
                    "windowIndex": 4,
                    "transitionOutcome": "completed",
                    "currentObjective": "Deliver parity brief.",
                    "currentFocus": "final-delivery.",
                    "responseRequirementsDigest": "req_final",
                    "restartMessageDigest": "restart_final",
                    "protectedRefIds": ["node_b"],
                    "workTreeCurrentNodeId": "work-tree-node_final",
                    "workTreeStatus": "completed",
                    "workTreeRecoveryAnchor": "resume:final",
                    "stateFingerprint": "state_final",
                    "memoryRetrievalState": {
                        "matchedNodeCount": 4,
                        "materializedNodeCount": 1,
                        "summary": "retrieval final",
                        "retrievalFingerprint": "retr_final",
                    },
                    "llm": {"planningStub0_1": 0},
                }
            ],
        },
    )

    audits = _build_window_execution_audits(evidence, local_db_match)

    assert audits[1]["runtimeWindowRecordCount"] == 1
    assert audits[1]["memoryTreeSignal"].startswith("runtime-window-record")
    assert audits[2]["classification"] == "repeated-carry-forward-window"
    assert audits[2]["runtimeWindowPlanningStub0_1"] == 1
    assert audits[3]["runtimeWindowOutcome"] == "completed"


def test_text_review_markdown_hides_optimization_sections() -> None:
    observation = {
        "id": "obs_text_review",
        "model": "LongCat-2.0-Preview",
        "metadata": {"traceId": "trace_text_review", "toolExecutionCount": 0},
        "input": {
            "messages": [
                {"role": "system", "content": "系统提示"},
                {"role": "user", "content": "用户任务"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "System intro: Project Yggdrasil mounts identity. "
                        "Top nodes: baseline evidence, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_initial. "
                        "Rehydrated 1 context items from snapshot snap_a and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Rehydrated 1 context items from snapshot snap_b and restored 25 runtime request fields. "
                        "Retrieved 4 nodes for query 'task'. Top nodes: required output structure, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_repeat. "
                        "Task goal: Produce the final release brief.\n"
                        "Task objective: Deliver the final result.\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "最终交付完成",
    }

    evidence = _build_observation_evidence(observation)
    audit = _build_observation_execution_audit(trace_id="trace_text_review", evidence=evidence, workspace_root=Path("."))
    markdown = _build_execution_audit_markdown(
        trace_id="trace_text_review",
        observations=[evidence],
        observation_audits=[audit],
        requested_provider="longcat",
        requested_model="LongCat-2.0-Preview",
        langfuse_base_url="http://127.0.0.1:3100",
    )

    assert "# Langfuse LLM Text Review" in markdown
    assert "### Initial Prompt Excerpts" in markdown
    assert "### Final Output Excerpt" in markdown
    assert "Optimization Recommendations" not in markdown
    assert "Raw Window Evidence" not in markdown


def test_execution_audit_payload_exposes_structured_windows() -> None:
    observation = {
        "id": "obs_payload",
        "model": "LongCat-2.0-Preview",
        "metadata": {"traceId": "trace_payload", "toolExecutionCount": 0},
        "input": {
            "messages": [
                {"role": "system", "content": "系统提示"},
                {
                    "role": "user",
                    "content": (
                        "<runtime_state>\n"
                        "System intro: Project Yggdrasil mounts identity. "
                        "Top nodes: baseline evidence, window policy. "
                        "Reverse trace anchored at work tree node work-tree-node_initial. "
                        "Task goal: Produce the final release brief.\n"
                        "Task objective: Deliver the final result.\n"
                        "</runtime_state>"
                    ),
                },
            ]
        },
        "output": "最终交付完成",
    }

    evidence = _build_observation_evidence(observation)
    audit = _build_observation_execution_audit(trace_id="trace_payload", evidence=evidence, workspace_root=Path("."))
    payload = _build_execution_audit_payload(
        trace_id="trace_payload",
        observations=[evidence],
        observation_audits=[audit],
        requested_provider="longcat",
        requested_model="LongCat-2.0-Preview",
        langfuse_base_url="http://127.0.0.1:3100",
    )

    assert payload["traceId"] == "trace_payload"
    assert payload["observationCount"] == 1
    assert payload["observations"][0]["taskGoal"] == "Produce the final release brief."
    assert payload["observations"][0]["windows"][0]["window"] == 1
    assert payload["observationAudits"][0]["observationId"] == "obs_payload"
