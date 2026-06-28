from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.contracts import TaskTakeoverProtocol
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel.execution_control import approve_task_completion, request_task_revision
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_task_takeover.plugin import TaskTakeoverModule  # noqa: F401  # Ensure module hooks are registered
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


def test_runtime_metrics_uses_window_span_floor_for_live_restart_paths() -> None:
    task = type(
        "TaskStub",
        (),
        {
            "window_index": 1,
            "restart_count": 0,
            "cumulative_window_span_tokens": 944,
            "carry_forward_loss_count": 0,
        },
    )()

    metrics = runtime_execution_loop._runtime_metrics(
        task,
        {
            "effectiveContextWindow": 64000,
            "windowRestartRatio": 0.75,
            "runtimeMetrics": {
                "windowIndex": 3,
                "restartCount": 2,
                "cumulativeWindowSpanTokens": 944,
                "carryForwardLossCount": 0,
            },
        },
    )

    assert metrics["windowIndex"] == 3
    assert metrics["restartCount"] == 2
    assert metrics["cumulativeWindowSpanTokens"] == 128000


def _simple_root_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "交付测试结果。",
        "objectiveSummary": "直接在根节点上完成交付。",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "交付测试结果。",
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
                    "questionsItAnswers": ["测试结果是什么"],
                    "nodeText": "完成交付。",
                    "localGoal": "完成交付。",
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


def _awaiting_approval_root_protocol(task_id: str) -> dict[str, object]:
    protocol = _simple_root_protocol(task_id)
    protocol["currentPhase"] = "deliver"
    protocol["status"] = "verified"
    work_tree = protocol["workTree"]
    assert isinstance(work_tree, dict)
    work_tree["status"] = "awaiting-approval"
    work_tree["pcMemo"] = "等待批准"
    nodes = work_tree["nodes"]
    assert isinstance(nodes, list)
    root = nodes[0]
    assert isinstance(root, dict)
    root["status"] = "completed"
    root["executionSummary"] = "根节点已完成，等待批准。"
    return protocol


def _seed_awaiting_approval_task(task_id: str, run_id: str) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "title": f"{task_id} awaiting approval",
                "goal": "验证显式 approval 控制面。",
                "status": "awaiting-approval",
                "currentObjective": "等待批准或重新打开修订。",
                "currentFocus": "awaiting-approval",
            }
        )
        task_repository.create_agent_run(
            task.id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": "LongCat-Flash-Lite",
                "selectedProvider": "longcat",
            },
        )
        runtime_takeover.persist_task_takeover_protocol(
            TaskTakeoverProtocol.model_validate(_awaiting_approval_root_protocol(task_id)),
            task_id=task.id,
            run_id=run_id,
        )


def _nested_work_tree_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "execute",
        "status": "executing",
        "objective": "完成两个子节点并回到根节点等待批准。",
        "objectiveSummary": "先完成 child-1，再完成 child-2，最后由 root 汇总。",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "完成两个子节点并回到根节点等待批准。",
            "status": "active",
            "currentNodeId": "child-1",
            "loadedNodeIds": ["root", "child-1", "child-2"],
            "activePathNodeIds": ["root", "child-1"],
            "pcMemo": "continue:child-1",
            "entropyBudgetRemaining": 8,
            "versionCounter": 1,
            "nodes": [
                {
                    "id": "root",
                    "title": "根节点",
                    "parentNodeId": None,
                    "questionsItAnswers": ["最终结论是什么"],
                    "nodeText": "汇总两个子节点的结果。",
                    "localGoal": "汇总两个子节点的结果。",
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
                    "questionsItAnswers": ["第一个子任务是否完成"],
                    "nodeText": "完成第一个子任务。",
                    "localGoal": "完成第一个子任务。",
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
                    "questionsItAnswers": ["第二个子任务是否完成"],
                    "nodeText": "完成第二个子任务。",
                    "localGoal": "完成第二个子任务。",
                    "workingNodeAnnotation": "<Working_Node: child-2>",
                    "phase": "executing",
                    "status": "pending",
                    "childNodeIds": [],
                    "detailLevel": 1,
                    "recoveryAnchor": "resume:child-2",
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


def _fake_completion_factory(text: str = "结果：完成。\n证据：通过。"):
    def _fake(*args, **kwargs):
        return {
            "assistantText": text,
            "invocation": {
                "id": "inv_p2_test",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p2_test",
                "traceId": "trace_p2_test",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }
    return _fake


def test_approve_task_completion_moves_to_completed() -> None:
    runtime = get_persistence_runtime()
    _seed_awaiting_approval_task("task_p2_approve_test", "run_p2_approve_test")

    # Approve
    result = approve_task_completion("task_p2_approve_test")
    assert result["status"] == "completed"
    assert result["task"]["status"] == "completed"

    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_p2_approve_test")
        assert task is not None
        assert task.status == "completed"


def test_request_task_revision_reopens_and_requeues(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = [0]
    def _fake(*args, **kwargs):
        call_count[0] += 1
        return {
            "assistantText": "结果：完成。\n证据：通过。",
            "invocation": {
                "id": f"inv_p2_revision_{call_count[0]}",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"artifact_p2_revision_{call_count[0]}",
                "traceId": f"trace_p2_revision_{call_count[0]}",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }
    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake)
    
    _seed_awaiting_approval_task("task_p2_revision_test", "run_p2_revision_test")

    # Request revision
    result = request_task_revision("task_p2_revision_test", {"reason": "需要补充证据。"})
    assert result["status"] == "queued"
    assert result["task"]["status"] == "queued"

    # Re-execute
    reprocessed = run_worker_once("agent-runtime")
    assert reprocessed["result"]["status"] == "awaiting-approval"


def test_approve_rejects_non_awaiting_approval_task() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_approve_reject",
            "title": "P2 approve reject test",
            "goal": "验证非 awaiting-approval 状态不能 approve。",
            "status": "draft",
        })

    with pytest.raises(ValueError, match="cannot be approved"):
        approve_task_completion("task_p2_approve_reject")


def test_delivery_gate_allows_task_relevant_delivery_without_optional_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_completion_factory(text="# result\n完成。\n# evidence\n通过。")
    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", fake)
    
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_gate_block",
            "title": "P2 delivery gate block",
            "goal": "验证缺少 optional delivery sections 不会阻断交付。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_gate_block/start",
        json={
            "currentObjective": "完成交付。",
            "takeoverProtocol": _simple_root_protocol("task_p2_gate_block"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    assert first["result"]["status"] == "completed"
    assert first["result"]["task"]["status"] == "completed"
    assert first["result"]["run"]["status"] == "completed"
    assert first["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "completed"


def test_delivery_gate_does_not_force_retry_for_optional_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    call_count = [0]

    def _fake(*args, **kwargs):
        call_count[0] += 1
        assistant_text = (
            "我先读取当前上下文并确认证据边界。"
            if call_count[0] == 1
            else "结果：完成。\n证据：通过。"
        )
        return {
            "assistantText": assistant_text,
            "invocation": {
                "id": f"inv_p2_gate_retry_{call_count[0]}",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"artifact_p2_gate_retry_{call_count[0]}",
                "traceId": f"trace_p2_gate_retry_{call_count[0]}",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake)
    
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_gate_retry_success",
            "title": "P2 delivery gate retry success",
            "goal": "验证缺少 optional sections 不触发格式型重试。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_gate_retry_success/start",
        json={
            "currentObjective": "完成交付。",
            "takeoverProtocol": _simple_root_protocol("task_p2_gate_retry_success"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    assert first["result"]["status"] == "awaiting-approval"
    assert first["result"]["task"]["status"] == "awaiting-approval"
    assert first["result"]["run"]["status"] == "completed"
    assert first["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "awaiting-approval"
    assert call_count[0] == 1


def test_work_tree_revision_and_approve_stay_in_same_multinode_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(*args, **kwargs):
        request = kwargs["request"]
        current_node_id = str(request.get("currentNodeId") or "")
        work_tree_nodes = (request.get("takeoverProtocol") or {}).get("workTree", {}).get("nodes") or []
        completed_children = sorted(
            str(node.get("id"))
            for node in work_tree_nodes
            if isinstance(node, dict)
            and str(node.get("parentNodeId") or "") == "root"
            and str(node.get("status") or "") == "completed"
        )
        text_by_node = {
            "child-1": "子节点一完成。证据：child-1 证据齐全。下一步继续 child-2。",
            "child-2": "子节点二完成。证据：child-2 证据齐全。下一步汇总 root。",
            "root": "根节点已汇总两个子节点。证据：已形成最终答案。等待显式批准。",
        }
        assistant_text = text_by_node[current_node_id]
        if current_node_id == "root" and completed_children == ["child-1"]:
            assistant_text = "root 继续编排并进入 child-2。\n<work-node-enter nodeId=\"child-2\"></work-node-enter>"
        return {
            "assistantText": assistant_text,
            "invocation": {
                "id": f"inv_p2_multinode_{current_node_id}",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": f"artifact_p2_multinode_{current_node_id}",
                "traceId": f"trace_p2_multinode_{current_node_id}",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake)
    
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_multinode_revision_approve",
            "title": "P2 multinode revision approve",
            "goal": "验证多节点工作树在同一条链上完成 revision 复跑与 approve。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_multinode_revision_approve/start",
        json={
            "currentObjective": "先完成子节点，再汇总根节点。",
            "currentFocus": "child-1",
            "takeoverProtocol": _nested_work_tree_protocol("task_p2_multinode_revision_approve"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    assert first["result"]["status"] == "continuing"
    assert first["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert first["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"

    second = run_worker_once("agent-runtime")
    assert second["result"]["status"] == "continuing"
    assert second["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "child-2"
    assert second["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "enter-existing-child"

    third = run_worker_once("agent-runtime")
    assert third["result"]["status"] == "continuing"
    assert third["result"]["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert third["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"

    fourth = run_worker_once("agent-runtime")
    assert fourth["result"]["status"] == "awaiting-approval"
    assert fourth["result"]["task"]["status"] == "awaiting-approval"
    assert fourth["result"]["windowExecutionArtifact"]["record"]["transitionOutcome"] == "awaiting-approval"

    revision = request_task_revision(
        "task_p2_multinode_revision_approve",
        {"reason": "请补充根节点交付说明。", "nodeId": "root"},
    )
    assert revision["status"] == "queued"
    assert revision["task"]["status"] == "queued"
    assert revision["takeoverProtocol"]["workTree"]["currentNodeId"] == "root"

    rerun = run_worker_once("agent-runtime")
    assert rerun["result"]["status"] == "awaiting-approval"
    assert rerun["result"]["task"]["status"] == "awaiting-approval"

    approval = approve_task_completion("task_p2_multinode_revision_approve")
    assert approval["status"] == "completed"
    assert approval["task"]["status"] == "completed"

    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_p2_multinode_revision_approve")
        assert task is not None
        assert task.status == "completed"
