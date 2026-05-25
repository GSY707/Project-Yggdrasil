from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel.execution_control import approve_task_completion, request_task_revision
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_part_b as runtime_execution_loop_part_b
from yggdrasil_task_takeover.plugin import TaskTakeoverModule  # Ensure module hooks are registered
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


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


def _fake_completion_factory(text: str = "# result\n完成。\n# evidence\n通过。\n# pending\n无。\n# incomplete\n无。"):
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


def test_approve_task_completion_moves_to_completed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_completion_factory()
    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", fake)
    monkeypatch.setattr(runtime_execution_loop_part_b, "invoke_runtime_completion", fake)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_approve_test",
            "title": "P2 approve test",
            "goal": "验证 approve 闭环。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_approve_test/start",
        json={
            "currentObjective": "完成交付。",
            "takeoverProtocol": _simple_root_protocol("task_p2_approve_test"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["result"]["status"] == "awaiting-approval"

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
            "assistantText": "# result\n完成。\n# evidence\n通过。\n# pending\n无。\n# incomplete\n无。",
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
    monkeypatch.setattr(runtime_execution_loop_part_b, "invoke_runtime_completion", _fake)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task({
            "id": "task_p2_revision_test",
            "title": "P2 revision test",
            "goal": "验证 revision 闭环。",
            "status": "draft",
        })

    started = client.post(
        "/runtime/tasks/task_p2_revision_test/start",
        json={
            "currentObjective": "完成交付。",
            "takeoverProtocol": _simple_root_protocol("task_p2_revision_test"),
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["result"]["status"] == "awaiting-approval"

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
