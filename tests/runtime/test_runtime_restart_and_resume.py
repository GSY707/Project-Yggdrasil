import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa
import yggdrasil_model_providers

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_agent_runtime.runtime import build_root_mount_package, prepare_pause_snapshot
from yggdrasil_context_pruning.plugin import ContextPruningModule
from yggdrasil_sdk import PromptAssetRepository, TaskRepository, get_persistence_runtime, resolve_workspace_root
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.orm import RetrievalRequestORM
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
import yggdrasil_sdk.runtime_kernel.execution_loop_part_b as runtime_execution_loop_part_b
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow

def test_main_agent_runtime_window_restart_closed_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_window_restart",
                "title": "伪无限上下文窗口闭环",
                "goal": "当工作集超过人工限制的有效窗口时，自动生成 carry-forward package 并切换到下一窗口继续执行。",
                "status": "draft",
                "currentObjective": "验证自动窗口重启和续跑闭环。",
                "currentFocus": "window-restart",
                "resumeMessage": "继续执行下一窗口。",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append({
            "resumeMessage": request_payload.get("resumeMessage"),
            "restartMetrics": request_payload.get("runtimeMetrics"),
        })
        return {
            "assistantText": "已根据 carry-forward package 继续执行并完成当前窗口目标。",
            "invocation": {
                "id": f"inv_window_restart_{len(invoke_calls)}",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_window_restart",
                "traceId": "trace_window_restart",
            },
            "usage": {
                "inputTokens": 64,
                "outputTokens": 24,
                "totalTokens": 88,
            },
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {
                "compilePromptMs": 0.0,
                "modelToolLoopMs": 0.0,
            },
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    monkeypatch.setattr(runtime_execution_loop_part_b, "invoke_runtime_completion", _fake_invoke_runtime_completion)

    started = client.post(
        "/runtime/tasks/task_window_restart/start",
        json={
            "currentFocus": "执行人工受限窗口压力路径",
            "currentObjective": "验证超过 effectiveContextWindow 后自动切换窗口。",
            "currentContext": [
                {
                    "id": "ctx_window_large",
                    "title": "长任务主工作集",
                    "content": "正式上下文窗口压力样本。" * 80,
                    "importance": 0.99,
                }
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_window_large"}],
            "effectiveContextWindow": 120,
            "windowRestartRatio": 0.75,
            "restartMessage": "窗口已满，请基于 carry-forward package 在下一窗口继续执行。",
        },
    )
    assert started.status_code == 202

    first_run = run_worker_once("agent-runtime")
    assert first_run["status"] == "processed"
    assert first_run["result"]["status"] == "restarting"
    assert first_run["result"]["snapshot"]["snapshotType"] == "restart"
    assert first_run["result"]["queuedWorkItem"]["command"] == "resume"
    restart_window_artifact = first_run["result"]["windowExecutionArtifact"]
    restart_window_path = Path(resolve_workspace_root()) / restart_window_artifact["artifactRef"]["locator"]
    restart_window_payload = json.loads(restart_window_path.read_text(encoding="utf-8"))
    assert restart_window_payload["transitionOutcome"] == "restart-requested"
    assert restart_window_payload["restartTrigger"] == "effectiveContextWindow"
    assert restart_window_payload["targetSnapshotId"] == first_run["result"]["snapshot"]["id"]
    assert restart_window_payload["windowIndex"] == 1
    restart_request_state = next(
        action["requestState"]
        for action in first_run["result"]["snapshot"]["pendingActions"]
        if isinstance(action, dict) and action.get("kind") == "runtime-request-state"
    )
    restart_context = client.get(
        "/runtime/package-entry",
        params={"locator": first_run["result"]["snapshot"]["contextRef"]["locator"]},
    )
    assert restart_context.status_code == 200
    restart_carry_forward = restart_context.json()["payload"][0]
    assert restart_request_state["memoryRetrievalState"]["requestId"]
    assert restart_request_state["takeoverProtocol"]["workTree"]["currentNodeId"] is not None
    assert restart_carry_forward["pointerPackage"]["handoffMode"] == "execution-pointer"
    assert restart_carry_forward["pointerPackage"]["workTreeCurrentNodeId"] is not None
    assert restart_carry_forward["pointerPackage"]["retrievalFingerprint"] is not None
    assert "Carry-forward execution pointer W1 -> W2" in restart_carry_forward["content"]
    assert invoke_calls == []

    second_run = run_worker_once("agent-runtime")
    assert second_run["status"] == "processed"
    assert second_run["result"]["status"] == "completed"
    assert len(invoke_calls) == 1
    completed_window_artifact = second_run["result"]["windowExecutionArtifact"]
    completed_window_path = Path(resolve_workspace_root()) / completed_window_artifact["artifactRef"]["locator"]
    completed_window_payload = json.loads(completed_window_path.read_text(encoding="utf-8"))
    assert completed_window_payload["transitionOutcome"] == "completed"
    assert completed_window_payload["windowIndex"] == 2
    assert completed_window_payload["memoryRetrievalState"]["requestId"] is not None
    assert completed_window_payload["workTreeCurrentNodeId"] is not None
    assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["memoryRetrievalState"]["requestId"]
    assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["memoryRetrievalState"]["summary"] is not None
    assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["takeoverProtocol"]["workTree"]["currentNodeId"] is not None

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_window_restart")
        runs = task_repository.list_agent_runs("task_window_restart")
        assert task is not None
        assert task.status == "completed"
        assert task.restart_count == 1
        assert task.window_index == 2
        assert task.cumulative_window_span_tokens >= 120
        assert len(runs) == 2
        run_by_window_index = {run.window_index: run for run in runs}
        previous_run = run_by_window_index[1]
        latest_run = run_by_window_index[2]
        assert latest_run.parent_run_id == previous_run.id
        assert latest_run.window_index == 2
        assert previous_run.window_index == 1


def test_main_agent_runtime_pause_resume_closed_loop(monkeypatch) -> None:
    monkeypatch.setenv("YGGDRASIL_DISABLE_LIVE_LLM", "1")
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_runtime",
                "title": "主 Agent 第一条闭环",
                "goal": "完成启动、写入、暂停、恢复的最小正式闭环。",
                "status": "draft",
                "currentObjective": "完成首次执行并进入 safe-stop。",
                "currentFocus": "main-agent-runtime",
                "resumeMessage": "继续完成主 Agent 第一条闭环。",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_runtime/start",
        json={
            "currentFocus": "执行主 Agent 第一条闭环",
            "currentContext": [
                {
                    "id": "ctx_keep",
                    "title": "运行时协议",
                    "content": "主 Agent 需要 route decision、safe-stop、pause snapshot 和 resume 闭环。",
                    "importance": 0.9,
                },
                {
                    "id": "ctx_drop",
                    "title": "噪声上下文",
                    "content": "这段内容和当前任务关系较弱，可以被压缩。",
                    "importance": 0.1,
                },
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_keep"}],
        },
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"

    pause_requested = client.post(
        "/runtime/tasks/task_runtime/pause-request",
        json={
            "reason": "manual-pause-for-safe-stop",
            "resumeMessage": "继续完成主 Agent 第一条闭环。",
        },
    )
    assert pause_requested.status_code == 202

    first_run = run_worker_once("agent-runtime")
    assert first_run["status"] == "processed"
    assert first_run["result"]["status"] == "paused"
    assert first_run["result"]["runtimeTimings"]["buildRootMountMs"] >= 0
    assert first_run["result"]["runtimeTimings"]["llm"]["compilePromptMs"] >= 0
    snapshot = first_run["result"]["snapshot"]
    pause_request_state = next(
        action["requestState"]
        for action in snapshot["pendingActions"]
        if isinstance(action, dict) and action.get("kind") == "runtime-request-state"
    )
    assert pause_request_state["memoryRetrievalState"]["requestId"]
    assert pause_request_state["takeoverProtocol"]["workTree"]["currentNodeId"] is not None

    cached_root_mount = client.get(
        "/runtime/package-entry",
        params={"locator": snapshot["rootMountRef"]["locator"]},
    )
    assert cached_root_mount.status_code == 200
    assert cached_root_mount.json()["payload"]["taskId"] == "task_runtime"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task("task_runtime")
        assert task is not None
        assert task.status == "paused"
        assert task.active_snapshot_id == snapshot["id"]
        assert task.budget.token_budget_used > 0
        runs = task_repository.list_agent_runs("task_runtime")
        assert runs[0].status == "paused"
        assert runtime_repository.list_model_route_decisions(task_id="task_runtime")
        invocations = runtime_repository.list_model_invocations(task_id="task_runtime")
        assert len(invocations) == 1
        assert invocations[0].app_id == DEFAULT_APP_ID
        assert invocations[0].status == "fallback"
        assert invocations[0].prompt_compile_artifact_id is not None
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocations[0].prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.app_id == DEFAULT_APP_ID
        assert artifact.prompt_profile_version_id
        assert artifact.compiled_messages_ref is not None
        assert artifact.work_tree_snapshot is not None
        assert artifact.takeover_protocol_snapshot is not None
        assert artifact.work_tree_snapshot["currentNodeId"] is not None
        assert invocations[0].request_ref is not None
        assert invocations[0].response_ref is not None
        assert invocations[0].assistant_text_summary is not None
        assert any(label.startswith("work-tree:") for label in invocations[0].output_labels)
        request_path = Path(resolve_workspace_root()) / invocations[0].request_ref.locator
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert request_payload["appId"] == DEFAULT_APP_ID
        assert request_payload["promptCompileArtifactId"] == invocations[0].prompt_compile_artifact_id
        assert request_payload["promptMetadata"]["promptProfileId"] == "yggdrasil.main-agent"
        assert request_payload["promptMetadata"]["seedTemplateId"] == "yggdrasil.seed.generic.default"
        assert request_payload["promptMetadata"]["runType"] == "main"
        assert request_payload["promptMetadata"]["takeoverProtocol"]["objective"] == "完成首次执行并进入 safe-stop。"
        assert request_payload["promptMetadata"]["takeoverProtocol"]["appliedModules"] == ["task-takeover"]
        assert request_payload["promptMetadata"]["takeoverProtocol"]["workTree"]["status"] == "planned"
        response_path = Path(resolve_workspace_root()) / invocations[0].response_ref.locator
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
        assert isinstance(response_payload["assistantText"], str)
        assert response_payload["localRuntimeTimings"]["compilePromptMs"] >= 0
        assert response_payload["localRuntimeTimings"]["modelToolLoopMs"] >= 0
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 1
        assert "Task takeover protocol:" in execution_notes[0].content
        retrieval_requests = session.execute(sa.select(RetrievalRequestORM).order_by(RetrievalRequestORM.created_at.asc())).scalars().all()
        assert retrieval_requests
        assert any(record.work_tree_node_id is not None for record in retrieval_requests)
        assert any(record.reverse_trace_mode for record in retrieval_requests)

    assert first_run["result"]["takeoverProtocol"] is not None
    assert isinstance(first_run["result"]["assistantText"], str)
    assert first_run["result"]["takeoverProtocol"]["appliedModules"] == ["task-takeover"]
    assert first_run["result"]["takeoverProtocol"]["workTree"]["status"] == "verified"
    assert first_run["result"]["takeoverProtocolRef"] is not None

    resumed = client.post(
        "/runtime/tasks/task_runtime/resume",
        json={
            "resumeToken": snapshot["resumeToken"],
            "nextObjective": "完成恢复后的最后一次写入并收尾。",
        },
    )
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "queued"

    second_run = run_worker_once("agent-runtime")
    assert second_run["status"] == "processed"
    assert second_run["result"]["status"] == "completed"
    assert second_run["result"]["runtimeTimings"]["totalMs"] >= 0
    assert second_run["result"]["resume"] is not None
    assert second_run["result"]["rehydration"] is not None
    assert any("Rehydrated" in summary for summary in second_run["result"]["rehydration"]["summaries"])
    assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["takeoverProtocol"]["workTree"]["currentNodeId"] is not None

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task("task_runtime")
        assert task is not None
        assert task.status == "completed"
        assert task.active_snapshot_id is None
        runs = task_repository.list_agent_runs("task_runtime")
        assert len(runs) == 2
        assert {run.status for run in runs} == {"paused", "completed"}
        snapshots = task_repository.list_snapshots("task_runtime")
        assert snapshots[0].app_id == DEFAULT_APP_ID
        assert snapshots[0].status == "consumed"
        decisions = runtime_repository.list_model_route_decisions(task_id="task_runtime")
        assert len(decisions) == 2
        invocations = runtime_repository.list_model_invocations(task_id="task_runtime")
        assert len(invocations) == 2
        assert {invocation.app_id for invocation in invocations} == {DEFAULT_APP_ID}
        assert {invocation.status for invocation in invocations} == {"fallback"}
        assert all(invocation.assistant_text_summary for invocation in invocations)
        assert all(any(label.startswith("work-tree:") for label in invocation.output_labels) for invocation in invocations)
        for invocation in invocations:
            artifact = prompt_repository.get_prompt_compile_artifact(str(invocation.prompt_compile_artifact_id))
            assert artifact is not None
            assert artifact.work_tree_snapshot is not None
            assert artifact.takeover_protocol_snapshot is not None
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 2
    assert second_run["result"]["takeoverProtocol"] is not None
    assert second_run["result"]["takeoverProtocol"]["workTree"]["status"] == "completed"
    assert second_run["result"]["takeoverProtocolRef"] is not None


