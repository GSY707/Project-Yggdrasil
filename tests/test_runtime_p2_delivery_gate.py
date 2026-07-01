from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.contracts import TaskTakeoverProtocol
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel.execution_control import approve_task_completion, request_task_revision
from yggdrasil_sdk.runtime_kernel.execution_loop.state_memory import (
    _apply_parsed_assistant_work_tree_actions,
    _extract_assistant_work_tree_actions,
)
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop.transitions as runtime_transitions
from yggdrasil_task_takeover.plugin import TaskTakeoverModule  # noqa: F401  # Ensure module hooks are registered
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


def test_append_continuation_instruction_deduplicates_existing_tail() -> None:
    checkpoint = (
        "Child/leaf start checkpoint: before the first concrete tool call in this node, "
        "confirm this node's work scope, stopping point, and return path to the parent. "
        'After the stopping point is reached, output exactly one <work-node-complete status="completed">...</work-node-complete> '
        "directive with result, evidence, gaps/risks, and parent-next notes; do not declare the whole task complete from a child/leaf."
    )
    payload = {"responseRequirements": f"Output Markdown only. {checkpoint}"}

    runtime_transitions._append_continuation_instruction(payload, checkpoint)

    assert payload["responseRequirements"].count("Child/leaf start checkpoint") == 1
    assert payload["resumeMessage"] == checkpoint


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
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
            },
        )
        runtime_takeover.persist_task_takeover_protocol(
            TaskTakeoverProtocol.model_validate(_awaiting_approval_root_protocol(task_id)),
            task_id=task.id,
            run_id=run_id,
        )


def _completed_with_unfinished_work_tree_protocol(task_id: str) -> dict[str, object]:
    protocol = _simple_root_protocol(task_id)
    protocol["currentPhase"] = "deliver"
    protocol["status"] = "completed"
    work_tree = protocol["workTree"]
    assert isinstance(work_tree, dict)
    root_id = f"work-tree-{task_id}-root"
    leaf_id = f"work-tree-{task_id}-leaf"
    work_tree["rootNodeId"] = root_id
    work_tree["currentNodeId"] = leaf_id
    work_tree["loadedNodeIds"] = [root_id, leaf_id]
    work_tree["activePathNodeIds"] = [root_id, leaf_id]
    nodes = work_tree["nodes"]
    assert isinstance(nodes, list)
    root = nodes[0]
    assert isinstance(root, dict)
    root["id"] = root_id
    root["status"] = "completed"
    root["childNodeIds"] = [leaf_id]
    root["workingNodeAnnotation"] = f"<Working_Node: {root_id}>"
    nodes.append(
        {
            "id": leaf_id,
            "title": "未收束 leaf",
            "parentNodeId": root_id,
            "questionsItAnswers": ["还缺什么证据"],
            "nodeText": "leaf 已经做过部分工作，但没有回父节点收束。",
            "localGoal": "补齐证据并回父节点。",
            "workingNodeAnnotation": f"<Working_Node: {leaf_id}>",
            "phase": "executing",
            "status": "in-progress",
            "childNodeIds": [],
            "detailLevel": 1,
            "recoveryAnchor": f"resume:{leaf_id}",
        }
    )
    return protocol


def _completed_with_unfinished_child_protocol(task_id: str) -> dict[str, object]:
    protocol = _completed_with_unfinished_work_tree_protocol(task_id)
    work_tree = protocol["workTree"]
    assert isinstance(work_tree, dict)
    root_id = f"work-tree-{task_id}-root"
    leaf_id = f"work-tree-{task_id}-leaf"
    work_tree["currentNodeId"] = root_id
    nodes = work_tree["nodes"]
    assert isinstance(nodes, list)
    root = nodes[0]
    assert isinstance(root, dict)
    root["status"] = "completed"
    leaf = nodes[1]
    assert isinstance(leaf, dict)
    leaf["id"] = leaf_id
    leaf["parentNodeId"] = root_id
    leaf["status"] = "pending"
    return protocol


def _completed_with_unfinished_sibling_protocol(task_id: str) -> dict[str, object]:
    protocol = _completed_with_unfinished_work_tree_protocol(task_id)
    work_tree = protocol["workTree"]
    assert isinstance(work_tree, dict)
    root_id = f"work-tree-{task_id}-root"
    done_leaf_id = f"work-tree-{task_id}-done-leaf"
    pending_leaf_id = f"work-tree-{task_id}-pending-leaf"
    work_tree["currentNodeId"] = done_leaf_id
    work_tree["loadedNodeIds"] = [root_id, done_leaf_id, pending_leaf_id]
    work_tree["activePathNodeIds"] = [root_id, done_leaf_id]
    nodes = work_tree["nodes"]
    assert isinstance(nodes, list)
    root = nodes[0]
    assert isinstance(root, dict)
    root["childNodeIds"] = [done_leaf_id, pending_leaf_id]
    done_leaf = nodes[1]
    assert isinstance(done_leaf, dict)
    done_leaf.update(
        {
            "id": done_leaf_id,
            "title": "已完成 leaf",
            "parentNodeId": root_id,
            "status": "completed",
            "workingNodeAnnotation": f"<Working_Node: {done_leaf_id}>",
            "recoveryAnchor": f"resume:{done_leaf_id}",
        }
    )
    nodes.append(
        {
            "id": pending_leaf_id,
            "title": "未完成 sibling",
            "parentNodeId": root_id,
            "questionsItAnswers": ["还缺哪个路线"],
            "nodeText": "同级路线还没做。",
            "localGoal": "等待父节点调度。",
            "workingNodeAnnotation": f"<Working_Node: {pending_leaf_id}>",
            "phase": "executing",
            "status": "pending",
            "childNodeIds": [],
            "detailLevel": 1,
            "recoveryAnchor": f"resume:{pending_leaf_id}",
        }
    )
    return protocol


def _seed_completed_task_with_protocol(task_id: str, run_id: str, protocol_payload: dict[str, object]) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "title": f"{task_id} completed",
                "goal": "验证 completed revision 边界。",
                "status": "completed",
                "currentObjective": "完成态任务。",
                "currentFocus": "completed",
            }
        )
        task_repository.create_agent_run(
            task.id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
            },
        )
        runtime_takeover.persist_task_takeover_protocol(
            TaskTakeoverProtocol.model_validate(protocol_payload),
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
                "resolvedModel": "LongCat-2.0",
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
                "resolvedModel": "LongCat-2.0",
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


def test_request_task_revision_reopens_completed_task_with_unfinished_work_tree() -> None:
    task_id = "task_p2_completed_unfinished_revision"
    root_id = f"work-tree-{task_id}-root"
    _seed_completed_task_with_protocol(
        task_id,
        "run_p2_completed_unfinished_revision",
        _completed_with_unfinished_work_tree_protocol(task_id),
    )

    result = request_task_revision(
        task_id,
        {
            "nodeId": "root",
            "reason": "工作树还有未完成节点，先做任务控制分析，再继续执行。",
        },
    )

    assert result["status"] == "queued"
    assert result["task"]["status"] == "queued"
    work_tree = result["takeoverProtocol"]["workTree"]
    assert work_tree["currentNodeId"] == root_id
    assert work_tree["status"] == "active"


def test_request_task_revision_auto_unfinished_continues_current_node_with_unfinished_child() -> None:
    task_id = "task_p2_completed_unfinished_child_revision"
    root_id = f"work-tree-{task_id}-root"
    _seed_completed_task_with_protocol(
        task_id,
        "run_p2_completed_unfinished_child_revision",
        _completed_with_unfinished_child_protocol(task_id),
    )

    result = request_task_revision(
        task_id,
        {
            "nodeId": "auto-unfinished",
            "reason": "当前节点仍有未完成子节点，应该在当前节点继续安排。",
        },
    )

    work_tree = result["takeoverProtocol"]["workTree"]
    assert result["status"] == "queued"
    assert work_tree["currentNodeId"] == root_id
    assert work_tree["activePathNodeIds"] == [root_id]


def test_request_task_revision_auto_unfinished_bubbles_to_parent_when_sibling_unfinished() -> None:
    task_id = "task_p2_completed_unfinished_sibling_revision"
    root_id = f"work-tree-{task_id}-root"
    _seed_completed_task_with_protocol(
        task_id,
        "run_p2_completed_unfinished_sibling_revision",
        _completed_with_unfinished_sibling_protocol(task_id),
    )

    result = request_task_revision(
        task_id,
        {
            "nodeId": "auto-unfinished",
            "reason": "当前 leaf 已声明完成，但 sibling 未完成，应该回父节点继续调度。",
        },
    )

    work_tree = result["takeoverProtocol"]["workTree"]
    assert result["status"] == "queued"
    assert work_tree["currentNodeId"] == root_id
    assert work_tree["activePathNodeIds"] == [root_id]


def test_request_task_revision_defaults_to_control_analysis_and_auto_unfinished() -> None:
    task_id = "task_p2_default_control_revision"
    root_id = f"work-tree-{task_id}-root"
    _seed_completed_task_with_protocol(
        task_id,
        "run_p2_default_control_revision",
        _completed_with_unfinished_child_protocol(task_id),
    )

    result = request_task_revision(task_id, {})

    queued_payload = result["workItem"]["payload"]["payload"]
    work_tree = result["takeoverProtocol"]["workTree"]
    assert result["status"] == "queued"
    assert work_tree["currentNodeId"] == root_id
    assert queued_payload["workTreeDirectiveRequired"] is True
    assert "先做任务控制分析" in queued_payload["resumeMessage"]
    assert "Task Control Analysis" in queued_payload["responseRequirements"]
    assert "natural language never changes currentNodeId" in queued_payload["responseRequirements"]


def test_request_task_revision_rejects_completed_task_with_clean_work_tree() -> None:
    task_id = "task_p2_completed_clean_revision_reject"
    protocol = _awaiting_approval_root_protocol(task_id)
    protocol["status"] = "completed"
    work_tree = protocol["workTree"]
    assert isinstance(work_tree, dict)
    work_tree["status"] = "completed"
    _seed_completed_task_with_protocol(task_id, "run_p2_completed_clean_revision_reject", protocol)

    with pytest.raises(ValueError, match="cannot be reopened for revision"):
        request_task_revision(task_id, {"reason": "没有未完成工作树节点时不能重开。"})


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


def test_work_tree_directive_required_requeues_natural_language_leaf_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(*args, **kwargs):
        return {
            "assistantText": "现在创建并进入 leaf 2 做钠离子电池研究，然后给父节点 handoff。",
            "invocation": {
                "id": "inv_p2_work_tree_directive_required",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p2_work_tree_directive_required",
                "traceId": "trace_p2_work_tree_directive_required",
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
            "id": "task_p2_work_tree_directive_required",
            "title": "P2 work-tree directive required",
            "goal": "验证自然语言换节点不会改变工作树。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_work_tree_directive_required/start",
        json={
            "currentObjective": "先在父节点调度，再进入 leaf 执行。",
            "takeoverProtocol": _simple_root_protocol("task_p2_work_tree_directive_required"),
            "workTreeDirectiveRequired": True,
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    result = first["result"]
    assert result["status"] == "continuing"
    assert result["task"]["status"] == "queued"
    assert result["windowExecutionArtifact"]["record"]["transitionOutcome"] == "work-tree-directive-required"
    queued_payload = result["queuedWorkItem"]["payload"]["payload"]
    assert queued_payload["currentNodeId"] == "root"
    assert "工作树流程漂移提醒" in queued_payload["responseRequirements"]
    assert "workTreeDirectiveRequired" in queued_payload


def test_work_tree_directive_required_is_default_for_natural_language_leaf_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(*args, **kwargs):
        return {
            "assistantText": "现在创建并进入 leaf 2 做钠离子电池研究，然后给父节点 handoff。",
            "invocation": {
                "id": "inv_p2_work_tree_directive_required_default",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p2_work_tree_directive_required_default",
                "traceId": "trace_p2_work_tree_directive_required_default",
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
            "id": "task_p2_work_tree_directive_required_default",
            "title": "P2 default work-tree directive required",
            "goal": "验证自然语言换节点默认会被 runtime 纠偏。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_work_tree_directive_required_default/start",
        json={
            "currentObjective": "先在父节点调度，再进入 leaf 执行。",
            "takeoverProtocol": _simple_root_protocol("task_p2_work_tree_directive_required_default"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    result = first["result"]
    assert result["status"] == "continuing"
    assert result["windowExecutionArtifact"]["record"]["transitionOutcome"] == "work-tree-directive-required"
    queued_payload = result["queuedWorkItem"]["payload"]["payload"]
    assert queued_payload["currentNodeId"] == "root"
    assert queued_payload["workTreeDirectiveRequired"] is True
    assert "工作树流程漂移提醒" in queued_payload["responseRequirements"]


def test_work_tree_directive_required_also_catches_leaf_handoff_without_enter_parent() -> None:
    task_id = "task_p2_leaf_handoff_directive_required"
    protocol = TaskTakeoverProtocol.model_validate(_completed_with_unfinished_work_tree_protocol(task_id))
    actions = _extract_assistant_work_tree_actions(
        "## Leaf Handoff\n当前 leaf 已完成，返回父节点继续评估。",
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_leaf_handoff_directive_required",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert stack is not None
    assert result["directiveRequired"] is True
    assert result["transition"] == "work-tree-directive-required"
    assert result["currentNodeId"] == f"work-tree-{task_id}-leaf"
    assert "Leaf Handoff" in result["detectedClaims"]
    assert '<work-node-complete status="completed">' in result["correctionMessage"]


def test_work_node_complete_directive_bubbles_leaf_to_parent_with_summary() -> None:
    task_id = "task_p2_leaf_complete_directive"
    root_id = f"work-tree-{task_id}-root"
    leaf_id = f"work-tree-{task_id}-leaf"
    protocol = TaskTakeoverProtocol.model_validate(_completed_with_unfinished_work_tree_protocol(task_id))
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-complete status="completed">\n'
            "Result: Li-ion evidence collected.\n"
            "Evidence: search result A; fetch result B.\n"
            "Gaps/Risks: supply-chain uncertainty remains.\n"
            "Parent next: compare against sodium-ion.\n"
            "</work-node-complete>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_leaf_complete_directive",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "bubble-parent"
    assert result["requiresContinuation"] is True
    assert result["completedNodeIds"] == [leaf_id]
    assert updated_protocol.work_tree.current_node_id == root_id
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert nodes[leaf_id].status == "completed"
    assert "Li-ion evidence collected" in (nodes[leaf_id].execution_summary or "")
    parent_frame = next(frame for frame in stack.frames if frame.node_id == root_id)
    assert parent_frame.child_completion_summaries
    assert parent_frame.child_completion_summaries[-1].child_node_id == leaf_id
    assert "Li-ion evidence collected" in parent_frame.child_completion_summaries[-1].summary


def test_work_node_complete_confirm_children_closes_unfinished_subtree() -> None:
    task_id = "task_p2_complete_confirm_children"
    protocol_payload = _nested_work_tree_protocol(task_id)
    work_tree = protocol_payload["workTree"]
    assert isinstance(work_tree, dict)
    work_tree["currentNodeId"] = "root"
    protocol = TaskTakeoverProtocol.model_validate(protocol_payload)
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-complete status="completed" confirmChildren="true">\n'
            "Result: parent audited the report and child summaries; child-1 and child-2 are already absorbed.\n"
            "Evidence: final report and source table exist.\n"
            "Parent next: task can enter approval.\n"
            "</work-node-complete>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_complete_confirm_children",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "awaiting-approval"
    assert result["applied"][0]["confirmChildren"] is True
    assert set(result["confirmedCompletedDescendantNodeIds"]) == {"child-1", "child-2"}
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert {node_id: node.status for node_id, node in nodes.items()} == {
        "root": "completed",
        "child-1": "completed",
        "child-2": "completed",
    }


def test_work_node_update_directive_modifies_existing_node_without_creating_child() -> None:
    task_id = "task_p2_update_existing_node"
    protocol = TaskTakeoverProtocol.model_validate(_nested_work_tree_protocol(task_id))
    original_node_count = len(protocol.work_tree.nodes) if protocol.work_tree is not None else 0
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-update nodeId="child-2" title="补证据节点" '
            'questions="缺少哪些关键证据,下一步验证什么" evidence="pytest 输出,目录索引更新" status="in-progress">\n'
            "补齐提示词变更的验证和文档同步。\n"
            "</work-node-update>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_update_existing_node",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "update-work-node"
    assert result["updatedNodeIds"] == ["child-2"]
    assert len(updated_protocol.work_tree.nodes) == original_node_count
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert nodes["child-2"].title == "补证据节点"
    assert nodes["child-2"].local_goal == "补齐提示词变更的验证和文档同步。"
    assert nodes["child-2"].node_text == "补齐提示词变更的验证和文档同步。"
    assert nodes["child-2"].questions_it_answers == ["缺少哪些关键证据", "下一步验证什么"]
    assert nodes["child-2"].expected_evidence == ["pytest 输出", "目录索引更新"]
    assert nodes["child-2"].status == "in-progress"


def test_work_tree_multiple_state_directives_only_applies_first_transition() -> None:
    task_id = "task_p2_multiple_state_directives"
    protocol = TaskTakeoverProtocol.model_validate(_nested_work_tree_protocol(task_id))
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-enter nodeId="child-2"></work-node-enter>\n'
            '<work-node-complete status="completed">\n'
            "Result: child-2 finished in the same window.\n"
            "Evidence: should not be accepted for completion yet.\n"
            "</work-node-complete>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_multiple_state_directives",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "enter-existing-child"
    assert result["currentNodeId"] == "child-2"
    assert result["enteredNodeIds"] == ["child-2"]
    assert "completedNodeIds" not in result
    assert any(
        item.get("reason") == "multiple-work-tree-state-directives-in-one-window"
        for item in result["blocked"]
    )
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert nodes["child-2"].status == "in-progress"
    assert nodes["child-2"].execution_summary is None


def test_work_node_skip_directive_marks_obsolete_pending_child_skipped() -> None:
    task_id = "task_p2_skip_obsolete_child"
    protocol = TaskTakeoverProtocol.model_validate(_nested_work_tree_protocol(task_id))
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-skip nodeId="child-2">\n'
            "Obsolete: child-1 already answered this seeded planning branch, so child-2 should not block parent completion.\n"
            "</work-node-skip>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_skip_obsolete_child",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "work-tree-skip"
    assert result["requiresContinuation"] is True
    assert result["skippedNodeId"] == "child-2"
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert nodes["child-2"].status == "skipped"
    assert "Obsolete" in (nodes["child-2"].failure_summary or "")


def test_work_node_prune_directive_can_batch_skip_obsolete_placeholders() -> None:
    task_id = "task_p2_batch_prune_obsolete_placeholders"
    protocol = TaskTakeoverProtocol.model_validate(_nested_work_tree_protocol(task_id))
    actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-prune nodeIds="child-1,child-2">\n'
            "Both seeded placeholders are covered by the completed synthesis child and should not block root completion.\n"
            "</work-node-prune>"
        ),
        enabled=True,
    )

    updated_protocol, stack, result = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_batch_prune_obsolete_placeholders",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=actions,
    )

    assert updated_protocol is not None
    assert updated_protocol.work_tree is not None
    assert stack is not None
    assert result["transition"] == "work-tree-skip"
    assert result["skippedNodeIds"] == ["child-1", "child-2"]
    nodes = {node.id: node for node in updated_protocol.work_tree.nodes}
    assert nodes["child-1"].status == "skipped"
    assert nodes["child-2"].status == "skipped"


def test_work_node_prune_parent_with_leaf_requires_confirmation_before_skip() -> None:
    task_id = "task_p2_prune_parent_with_leaf_requires_confirmation"
    protocol_payload = _nested_work_tree_protocol(task_id)
    work_tree = protocol_payload["workTree"]
    assert isinstance(work_tree, dict)
    nodes = work_tree["nodes"]
    assert isinstance(nodes, list)
    child_2 = next(node for node in nodes if isinstance(node, dict) and node.get("id") == "child-2")
    child_2["childNodeIds"] = ["child-2-leaf"]
    nodes.append(
        {
            "id": "child-2-leaf",
            "title": "已完成叶子",
            "parentNodeId": "child-2",
            "questionsItAnswers": ["占位节点是否已覆盖"],
            "nodeText": "已完成的叶子节点。",
            "localGoal": "证明父节点可以清理已覆盖子树。",
            "workingNodeAnnotation": "<Working_Node: child-2-leaf>",
            "phase": "executing",
            "status": "completed",
            "executionSummary": "叶子已经完成，父节点确认后可清理占位父节点。",
            "childNodeIds": [],
            "detailLevel": 2,
            "recoveryAnchor": "resume:child-2-leaf",
        }
    )
    protocol = TaskTakeoverProtocol.model_validate(protocol_payload)

    first_actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-prune nodeId="child-2">\n'
            "child-2 is an obsolete seeded placeholder covered by the final synthesis.\n"
            "</work-node-prune>"
        ),
        enabled=True,
    )
    first_protocol, _stack, first = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_prune_parent_with_leaf_requires_confirmation",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=protocol,
        parsed_actions=first_actions,
    )

    assert first_protocol is not None
    assert first["transition"] == "work-tree-prune-confirm-required"
    assert first["confirmRequired"][0]["nodeId"] == "child-2"
    assert first["confirmRequired"][0]["reason"] == "terminal-descendants-confirmation-required"
    nodes_after_first = {node.id: node for node in first_protocol.work_tree.nodes}
    assert nodes_after_first["child-2"].status == "pending"

    confirmed_actions = _extract_assistant_work_tree_actions(
        (
            '<work-node-prune nodeId="child-2" confirmChildren="true">\n'
            "Confirmed by parent: child-2 leaf output is covered by final synthesis, so this subtree is obsolete.\n"
            "</work-node-prune>"
        ),
        enabled=True,
    )
    confirmed_protocol, _stack, confirmed = _apply_parsed_assistant_work_tree_actions(
        task_id=task_id,
        agent_run_id="run_p2_prune_parent_with_leaf_confirmed",
        request={"workTreeDirectiveRequired": True},
        root_mount={},
        takeover_protocol=first_protocol,
        parsed_actions=confirmed_actions,
    )

    assert confirmed_protocol is not None
    assert confirmed["transition"] == "work-tree-skip"
    assert confirmed["skippedNodeIds"] == ["child-2"]
    nodes_after_confirm = {node.id: node for node in confirmed_protocol.work_tree.nodes}
    assert nodes_after_confirm["child-2"].status == "skipped"
    assert nodes_after_confirm["child-2-leaf"].status == "completed"


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
                "resolvedModel": "LongCat-2.0",
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


def test_child_completion_with_missing_web_evidence_bubbles_to_parent(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake(*args, **kwargs):
        return {
            "assistantText": "结果：child-1 已完成初步资料归纳。\n证据：只有本轮摘要，缺少可验证 URL，需要父节点改派补证。",
            "invocation": {
                "id": "inv_p2_child_web_gap",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_p2_child_web_gap",
                "traceId": "trace_p2_child_web_gap",
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
            "id": "task_p2_child_web_gap_bubble",
            "title": "P2 child web gap bubble",
            "goal": "验证 child 缺 web 证据时返回父节点而不是挡死整棵树。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_child_web_gap_bubble/start",
        json={
            "currentObjective": "先完成 child，再由父节点评估是否补证。",
            "responseRequirements": "Need web-grounded answer with source URL citations.",
            "currentFocus": "child-1",
            "takeoverProtocol": _nested_work_tree_protocol("task_p2_child_web_gap_bubble"),
        },
    )
    assert started.status_code == 202

    first = run_worker_once("agent-runtime")
    result = first["result"]
    assert result["status"] == "continuing"
    assert result["task"]["status"] == "queued"
    assert result["queuedWorkItem"]["payload"]["payload"]["currentNodeId"] == "root"
    assert result["windowExecutionArtifact"]["record"]["transitionOutcome"] == "bubble-parent"

    work_tree = result["takeoverProtocol"]["workTree"]
    nodes = {node["id"]: node for node in work_tree["nodes"]}
    assert nodes["child-1"]["status"] == "completed"
    assert "缺少可验证 URL" in nodes["child-1"]["executionSummary"]


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
                "resolvedModel": "LongCat-2.0",
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
    assert "Child/leaf start checkpoint" in second["result"]["queuedWorkItem"]["payload"]["payload"]["responseRequirements"]
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
