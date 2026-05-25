from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
import yggdrasil_model_providers
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_part_b as runtime_execution_loop_part_b
from yggdrasil_sdk.runtime_kernel.takeover import (
    build_takeover_continuation_request,
    normalize_takeover_runtime_state,
)
from yggdrasil_sdk.runtime_kernel.snapshot import _build_restart_request_state
from yggdrasil_sdk.contracts import TaskTakeoverProtocol
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


def _root_only_takeover_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "稳定性硬化测试。",
        "objectiveSummary": "直接在根节点上测试。",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "稳定性硬化测试。",
            "status": "active",
            "currentNodeId": "root",
            "loadedNodeIds": ["root"],
            "activePathNodeIds": ["root"],
            "pcMemo": "continue:root",
            "entropyBudgetRemaining": 9,
            "versionCounter": 1,
            "nodes": [
                {
                    "id": "root",
                    "title": "根节点",
                    "parentNodeId": None,
                    "questionsItAnswers": ["测试"],
                    "nodeText": "测试。",
                    "localGoal": "测试。",
                    "workingNodeAnnotation": "<Working_Node: root>",
                    "phase": "delivery",
                    "status": "in-progress",
                    "childNodeIds": [],
                    "detailLevel": 0,
                    "recoveryAnchor": "resume:root",
                },
            ],
        },
        "deliverySections": [],
        "verificationItems": [],
        "metrics": {
            "planQualityScore0_100": 90.0,
            "reworkCount": 0,
            "reworkRate": 0.0,
            "clarificationNeeded": False,
            "deliveryCompletenessScore0_100": 0.0,
            "verificationPassRate": 0.0,
        },
        "appliedModules": ["task-takeover"],
        "hookTrace": [],
    }


def _nested_takeover_protocol(task_id: str) -> dict[str, object]:
    protocol = _root_only_takeover_protocol(task_id)
    protocol["workTree"]["nodes"] = [
        {
            "id": "root",
            "title": "汇总根节点",
            "parentNodeId": None,
            "questionsItAnswers": ["最终结果"],
            "nodeText": "汇总子节点。",
            "localGoal": "汇总子节点。",
            "workingNodeAnnotation": "<Working_Node: root>",
            "phase": "delivery",
            "status": "in-progress",
            "childNodeIds": ["child-1", "child-2"],
            "detailLevel": 0,
            "recoveryAnchor": "resume:root",
        },
        {
            "id": "child-1",
            "title": "子节点一",
            "parentNodeId": "root",
            "questionsItAnswers": ["子节点一"],
            "nodeText": "执行子节点一。",
            "localGoal": "执行子节点一。",
            "workingNodeAnnotation": "<Working_Node: child-1>",
            "phase": "executing",
            "status": "in-progress",
            "childNodeIds": [],
            "detailLevel": 1,
            "recoveryAnchor": "resume:child-1",
        },
        {
            "id": "child-2",
            "title": "子节点二",
            "parentNodeId": "root",
            "questionsItAnswers": ["子节点二"],
            "nodeText": "执行子节点二。",
            "localGoal": "执行子节点二。",
            "workingNodeAnnotation": "<Working_Node: child-2>",
            "phase": "executing",
            "status": "pending",
            "childNodeIds": [],
            "detailLevel": 1,
            "recoveryAnchor": "resume:child-2",
        },
    ]
    protocol["workTree"]["loadedNodeIds"] = ["root", "child-1", "child-2"]
    protocol["workTree"]["activePathNodeIds"] = ["root", "child-1"]
    protocol["workTree"]["currentNodeId"] = "child-1"
    return protocol


# ============================================================
# E1: Runtime Hard Block Tests
# ============================================================

def test_runtime_hard_blocks_tool_calls_when_tool_execution_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """allowToolExecution=false 时模型返回的 toolCalls 应被静默丢弃。"""

    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "hardening-model",
                "provider": "hardening-provider",
                "quality": 0.8,
                "costPer1k": 0.001,
                "latencyMs": 50,
                "contextWindow": 1_000_000,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        return {
            "mode": "live",
            "provider": "hardening-provider",
            "model": "hardening-model",
            "outputText": "# result\n直接输出。\n# evidence\n无需工具。\n# pending\n无。\n# incomplete\n无。",
            "finishReason": "stop",
            "usage": {"inputTokens": 100, "outputTokens": 50, "totalTokens": 150},
            "costUsed": 0.0,
            "error": None,
            "toolCalls": [
                {
                    "id": "call_unexpected_1",
                    "name": "mcp.read.read_file",
                    "arguments": {"path": "/etc/passwd"},
                }
            ],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "直接输出。"},
                    }
                ],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            },
            "requestPayload": {"model": "hardening-model", "messages": [], "stream": True},
            "firstTokenLatencyMs": 50.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_e1_hard_block",
                "title": "E1 hard block test",
                "goal": "验证 tool call 被 runtime 硬拦截。",
                "status": "draft",
                "budgetState": {"tokenBudgetTotal": 1000, "costBudgetTotal": 5.0},
            }
        )

    started = client.post(
        "/runtime/tasks/task_e1_hard_block/start",
        json={
            "allowToolExecution": False,
            "currentObjective": "测试硬拦截。",
            "takeoverProtocol": _root_only_takeover_protocol("task_e1_hard_block"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    # 关键断言：task 应正常完成，不因 tool 执行失败而 crash
    assert processed["result"]["status"] == "awaiting-approval"
    # toolExecutions 应为空（tool calls 被丢弃）
    tool_execs = processed["result"].get("windowExecutionArtifact", {}).get("record", {}).get("toolExecutions") or []
    assert len(tool_execs) == 0


# ============================================================
# E2: Continuation Parameter Inheritance Tests
# ============================================================

def test_continuation_inherits_thinking_and_reasoning_effort() -> None:
    """验证 build_takeover_continuation_request 继承 thinking 和 reasoningEffort。"""
    base_request = {
        "appId": "app1",
        "projectId": "proj1",
        "taskType": "coding",
        "allowToolExecution": False,
        "temperature": 0.2,
        "maxTokens": 512,
        "thinking": "enabled",
        "reasoningEffort": "high",
        "candidateModels": [
            {"model": "TestModel", "provider": "test", "quality": 0.9, "costPer1k": 0.0, "latencyMs": 100, "contextWindow": 128000}
        ],
    }
    protocol = TaskTakeoverProtocol.model_validate(
        _root_only_takeover_protocol("task_e2_thinking")
    )
    protocol, stack = normalize_takeover_runtime_state(
        protocol, task_id="task_e2_thinking", agent_run_id="run_e2_thinking"
    )
    continuation = build_takeover_continuation_request(
        base_request, protocol=protocol, work_context_stack=stack
    )
    assert continuation["thinking"] == "enabled"
    assert continuation["reasoningEffort"] == "high"
    assert continuation["allowToolExecution"] is False
    assert continuation["temperature"] == 0.2
    assert continuation["maxTokens"] == 512


def test_continuation_inherits_forced_window_restart_budget() -> None:
    """验证 forcedWindowRestartBudget 被继承。"""
    base_request = {
        "taskType": "coding",
        "forcedWindowRestartBudget": 3,
    }
    protocol = TaskTakeoverProtocol.model_validate(
        _root_only_takeover_protocol("task_e2_forced_budget")
    )
    protocol, stack = normalize_takeover_runtime_state(
        protocol, task_id="task_e2_forced_budget", agent_run_id="run_e2_forced_budget"
    )
    continuation = build_takeover_continuation_request(
        base_request, protocol=protocol, work_context_stack=stack
    )
    assert continuation["forcedWindowRestartBudget"] == 3


# ============================================================
# E3: Policy Drift Regression Tests
# ============================================================

def test_sibling_continuation_preserves_provider_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    """验证 child-1 → child-2 sibling continuation 不改变 provider policy。"""
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_e3_sibling_policy",
                "title": "E3 sibling policy preservation",
                "goal": "验证 sibling continuation 不改变 provider policy。",
                "status": "draft",
            }
        )

    call_count = [0]

    def _fake(*args, **kwargs):
        request = kwargs["request"]
        call_count[0] += 1
        current_node_id = str(request.get("currentNodeId") or "")
        text_by_node = {
            "child-1": "# result\n子节点一完成。\n# evidence\nok。\n# pending\n无。\n# incomplete\n无。",
            "child-2": "# result\n子节点二完成。\n# evidence\nok。\n# pending\n无。\n# incomplete\n无。",
            "root": "# result\n根节点完成。\n# evidence\nok。\n# pending\n无。\n# incomplete\n无。",
        }
        return {
            "assistantText": text_by_node.get(current_node_id, text_by_node["root"]),
            "invocation": {
                "id": f"inv_e3_{call_count[0]}",
                "resolvedModel": "LongCat-2.0-Preview",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"art_e3_{call_count[0]}",
                "traceId": f"trace_e3_{call_count[0]}",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake)
    monkeypatch.setattr(runtime_execution_loop_part_b, "invoke_runtime_completion", _fake)

    POLICY_PARAMS = {
        "allowToolExecution": False,
        "temperature": 0.15,
        "maxTokens": 256,
        "allowModelFallback": False,
        "candidateModels": [
            {
                "model": "LongCat-2.0-Preview",
                "provider": "longcat",
                "quality": 0.82,
                "costPer1k": 0.0,
                "latencyMs": 760,
                "contextWindow": 128000,
            }
        ],
    }

    started = client.post(
        "/runtime/tasks/task_e3_sibling_policy/start",
        json={
            **POLICY_PARAMS,
            "currentObjective": "测试 sibling continuation policy。",
            "currentFocus": "child-1",
            "takeoverProtocol": _nested_takeover_protocol("task_e3_sibling_policy"),
        },
    )
    assert started.status_code == 202

    # Round 1: child-1 完成 → continuation 到 child-2
    first = run_worker_once("agent-runtime")
    assert first["status"] == "processed"
    assert first["result"]["status"] == "continuing"

    queued = first["result"]["queuedWorkItem"]["payload"]
    assert queued["currentNodeId"] == "child-2"
    assert queued["allowToolExecution"] is False
    assert queued["temperature"] == 0.15
    assert queued["maxTokens"] == 256
    assert queued["candidateModels"][0]["model"] == "LongCat-2.0-Preview"
    assert queued["candidateModels"][0]["provider"] == "longcat"

    # Round 2: child-2 完成 → bubble 到 root
    second = run_worker_once("agent-runtime")
    assert second["status"] == "processed"

    if second["result"]["status"] == "continuing":
        root_payload = second["result"]["queuedWorkItem"]["payload"]
        assert root_payload["currentNodeId"] == "root"
        assert root_payload["allowToolExecution"] is False
        assert root_payload["temperature"] == 0.15
        assert root_payload["maxTokens"] == 256
        assert root_payload["candidateModels"][0]["model"] == "LongCat-2.0-Preview"

        # Round 3: root 完成 → awaiting-approval
        third = run_worker_once("agent-runtime")
        assert third["result"]["status"] == "awaiting-approval"
