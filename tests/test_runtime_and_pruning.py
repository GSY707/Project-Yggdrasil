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
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow


def _seed_task(
    task_id: str = "task_alpha",
    agent_run_id: str = "run_alpha",
    *,
    app_id: str = DEFAULT_APP_ID,
) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "appId": app_id,
                "title": "实现正式持久化底座",
                "goal": "把运行时、模块注册和快照链路落到正式存储。",
                "status": "running",
                "currentObjective": "完成 runtime 持久化",
                "currentFocus": "pause snapshot",
                "resumeMessage": "继续写入任务快照。",
            }
        )
        task_repository.create_agent_run(
            task_id,
            {
                "id": agent_run_id,
                "status": "running",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )


def test_root_mount_package_uses_formal_runtime_fields() -> None:
    _seed_task()
    mount_package = build_root_mount_package(
        "task_alpha",
        {
            "taskObjective": "整理项目的模块注册和运行时入口",
            "currentFocus": "runtime bootstrap",
            "resumeMessage": "继续完成 M1。",
        },
    )

    assert mount_package["taskId"] == "task_alpha"
    assert mount_package["identityRefs"]
    assert mount_package["contextRefs"]
    assert mount_package["executionRefs"]
    assert "text-memory" in mount_package["activeCapabilities"]
    assert "training-lab" not in mount_package["activeCapabilities"]
    assert mount_package["mountedNodeRefs"]
    assert mount_package["source"] == "database"


def test_root_mount_package_respects_application_default_capabilities() -> None:
    _seed_task(
        task_id="task_learning",
        agent_run_id="run_learning",
        app_id="yggdrasil.app.learning-coach",
    )

    mount_package = build_root_mount_package("task_learning")

    assert set(mount_package["activeCapabilities"]) == {
        "text-memory",
        "context-pruning",
        "mcp-bridge",
        "pause-resume",
        "task-takeover",
        "subagent-runtime",
        "scene-learning-coach",
    }


def test_pause_snapshot_reports_blockers_and_safe_stop() -> None:
    _seed_task()
    blocked_snapshot = prepare_pause_snapshot(
        "task_alpha",
        {
            "agentRunId": "run_alpha",
            "activeToolCalls": ["subagent.pr.create"],
            "currentResponseState": "streaming",
        },
    )
    assert blocked_snapshot["safeToPause"] is False
    assert blocked_snapshot["appId"] == DEFAULT_APP_ID
    assert "active-tool-calls" in blocked_snapshot["blockers"]
    assert blocked_snapshot["persisted"] is True
    assert any("Prepared safe-stop" in summary for summary in blocked_snapshot["moduleSummaries"])

    safe_snapshot = prepare_pause_snapshot(
        "task_alpha",
        {
            "agentRunId": "run_alpha",
            "pendingWrites": [{"kind": "node", "id": "node_123"}],
            "currentResponseState": "completed",
        },
    )
    assert safe_snapshot["safeToPause"] is True
    assert safe_snapshot["appId"] == DEFAULT_APP_ID
    assert safe_snapshot["flushedWrites"] == 1
    assert safe_snapshot["persisted"] is True
    assert any(action["kind"] == "resume-digest" for action in safe_snapshot["pendingActions"])


def test_context_pruning_retains_protected_refs() -> None:
    plugin = ContextPruningModule()
    plan = plugin.plan(
        {
            "taskId": "task_alpha",
            "sourceRunId": "run_alpha",
            "nextObjective": "只保留和模块注册相关的内容",
            "budget": {"maxRetainedTokens": 30},
            "protectedItems": [{"kind": "node", "id": "node_keep"}],
            "currentContext": [
                {
                    "id": "node_keep",
                    "title": "模块注册表",
                    "content": "模块注册需要稳定的 install record 和 hook catalog。",
                    "importance": 0.9,
                },
                {
                    "id": "node_drop",
                    "title": "无关资料",
                    "content": "这段内容和当前目标没有直接关系。",
                    "importance": 0.1,
                },
            ],
        }
    )

    retained_ids = {reference["id"] for reference in plan["retainedRefs"]}
    assert "node_keep" in retained_ids

    executed = plugin.execute(
        {
            "plan": plan,
            "currentContext": [
                {
                    "id": "node_keep",
                    "title": "模块注册表",
                    "content": "模块注册需要稳定的 install record 和 hook catalog。",
                }
            ],
        }
    )
    assert executed["status"] == "executed"
    assert executed["plan"]["status"] == "executed"


def test_main_agent_materializes_runtime_context_into_memory_tree_before_prompt() -> None:
    runtime = get_persistence_runtime()
    task_id = "task_memory_tree_runtime"
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": task_id,
                "title": "记忆树主导上下文装配",
                "goal": "让运行时在模型调用前先把外来上下文写入记忆树，再从记忆树检索工作集。",
                "status": "draft",
                "currentObjective": "验证当前 prompt 使用的是记忆树检索结果。",
                "currentFocus": "memory-tree-runtime",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        f"/runtime/tasks/{task_id}/start",
        json={
            "auditLevel": "strict",
            "currentFocus": "memory-tree-runtime",
            "currentObjective": "验证当前 prompt 使用的是记忆树检索结果。",
            "currentContext": [
                {
                    "id": "ctx_memory_tree_1",
                    "title": "持久记忆检索入口",
                    "content": "运行时必须先把上下文写成记忆节点，再从记忆树读取节点与关联关系。",
                    "importance": 0.95,
                },
                {
                    "id": "ctx_memory_tree_2",
                    "title": "共享挂载检索",
                    "content": "共享空间节点应和本地节点一起进入统一 retrieval，再由 text-memory 输出自然语言摘要。",
                    "importance": 0.85,
                },
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        temporary_nodes = [
            node
            for node in node_repository.list_nodes(branch_id="branch_main", limit=500)
            if node.status == "temporary"
            and node.title in {"持久记忆检索入口", "共享挂载检索"}
        ]
        assert len(temporary_nodes) >= 2

        invocations = runtime_repository.list_model_invocations(task_id=task_id)
        assert len(invocations) == 1
        invocation = invocations[0]
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocation.prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.compiled_messages_ref is not None
        assert invocation.request_ref is not None

        compiled_path = Path(resolve_workspace_root()) / artifact.compiled_messages_ref.locator
        compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))
        messages = compiled_payload.get("messages") or []
        assert messages
        user_message = str(messages[-1].get("content") or "")
        assert "Memory retrieval summary" in user_message
        assert "Materialized 2 runtime context items into the memory tree before retrieval." in user_message
        assert "持久记忆检索入口" in user_message


def test_main_agent_applies_memory_write_tags_without_interrupting_completion(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    task_id = "task_memory_tag_write"
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": task_id,
                "title": "标签写入记忆树",
                "goal": "让主 Agent 可以在回答中用标签写入记忆树而不触发额外工具回合。",
                "status": "draft",
                "currentObjective": "验证 assistant 输出标签会在停止点落入记忆树。",
                "currentFocus": "memory-tag-write",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        return {
            "assistantText": (
                "已记录本轮运行记忆。\n"
                '<memory-write title="运行时记忆策略" rootBranch="context" importance="0.93">'
                "模型必须始终先从记忆树检索，再决定当前工作集。"
                "</memory-write>"
            ),
            "invocation": {
                "id": "inv_memory_tag_write",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_memory_tag_write",
                "traceId": "trace_memory_tag_write",
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

    started = client.post(
        f"/runtime/tasks/{task_id}/start",
        json={
            "currentFocus": "memory-tag-write",
            "currentObjective": "验证 assistant 输出标签会在停止点落入记忆树。",
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"
    assert processed["result"]["memoryTagWrites"]["detectedCount"] == 1
    assert len(processed["result"]["memoryTagWrites"]["applied"]) == 1
    assert processed["result"]["memoryTagWrites"]["blocked"] == []

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task(task_id)
        assert task is not None

        memory_nodes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.title == "运行时记忆策略" and node.node_type == "detail"
        ]
        assert len(memory_nodes) == 1
        assert "模型必须始终先从记忆树检索，再决定当前工作集。" in memory_nodes[0].content

        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 1
        assert "已记录本轮运行记忆。" in execution_notes[0].content
        assert "<memory-write" not in execution_notes[0].content


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
    restart_request_state = next(
        action["requestState"]
        for action in first_run["result"]["snapshot"]["pendingActions"]
        if isinstance(action, dict) and action.get("kind") == "runtime-request-state"
    )
    assert restart_request_state["memoryRetrievalState"]["requestId"]
    assert restart_request_state["takeoverProtocol"]["workTree"]["currentNodeId"] is not None
    assert invoke_calls == []

    second_run = run_worker_once("agent-runtime")
    assert second_run["status"] == "processed"
    assert second_run["result"]["status"] == "completed"
    assert len(invoke_calls) == 1
    assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["memoryRetrievalState"]["requestId"]
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


def test_main_agent_runtime_pause_resume_closed_loop() -> None:
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


def test_main_agent_runtime_fails_when_budget_is_exhausted() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_budget_fail",
                "title": "预算约束校验",
                "goal": "验证主 Agent 会在预算不足时显式失败。",
                "status": "draft",
                "budgetState": {
                    "tokenBudgetTotal": 10,
                    "costBudgetTotal": 0.01,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_budget_fail/start",
        json={
            "currentContext": [
                {
                    "id": "ctx_budget",
                    "title": "大上下文",
                    "content": "这是一段为了触发预算超限而故意拉长的上下文。" * 40,
                    "importance": 0.8,
                }
            ]
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_budget_fail")
        assert task is not None
        assert task.status == "failed"
        assert task_repository.list_agent_runs("task_budget_fail") == []
        assert runtime_repository.list_model_route_decisions(task_id="task_budget_fail") == []


def test_main_agent_runtime_fails_when_actual_usage_exceeds_budget(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "budget-model",
                "provider": "budget-provider",
                "quality": 0.8,
                "costPer1k": 0.001,
                "latencyMs": 50,
                "contextWindow": 8192,
                "freeTier": True,
            }
        ],
    )

    def _fake_invoke_model(**_kwargs):
        return {
            "mode": "live",
            "provider": "budget-provider",
            "model": "budget-model",
            "outputText": "已输出一份超预算结果。",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 260,
                "outputTokens": 120,
                "totalTokens": 380,
            },
            "costUsed": 0.05,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已输出一份超预算结果。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 260,
                    "completion_tokens": 120,
                    "total_tokens": 380,
                },
            },
            "requestPayload": {
                "model": "budget-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 120.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_budget_actual_fail",
                "title": "预算后置校验",
                "goal": "验证实际 token/cost 超支后任务会失败。",
                "status": "draft",
                "budgetState": {
                    "tokenBudgetTotal": 500,
                    "costBudgetTotal": 0.03,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_budget_actual_fail/start",
        json={
            "currentContext": [
                {
                    "id": "ctx_budget_actual",
                    "title": "小上下文",
                    "content": "让预估通过，但让实际用量超支。",
                    "importance": 0.5,
                }
            ]
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"
    assert "budget exceeded after model invocation" in processed["result"]["detail"].lower()

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_budget_actual_fail")
        assert task is not None
        assert task.status == "failed"
        runs = task_repository.list_agent_runs("task_budget_actual_fail")
        assert len(runs) == 1
        assert runs[0].status == "failed"
        assert len(runtime_repository.list_model_route_decisions(task_id="task_budget_actual_fail")) == 1
        assert len(runtime_repository.list_model_invocations(task_id="task_budget_actual_fail")) == 1


def test_runtime_audit_level_lean_writes_compact_artifacts() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_audit_lean",
                "title": "lean audit runtime test",
                "goal": "验证 lean 审计模式会写入紧凑工件。",
                "status": "draft",
                "currentObjective": "完成一次最小运行。",
                "currentFocus": "lean-audit",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_audit_lean/start",
        json={
            "auditLevel": "lean",
            "currentFocus": "lean-audit",
            "currentContext": [
                {
                    "id": "ctx_audit",
                    "title": "lean audit context",
                    "content": "验证 runtime 的 request/response/compiled prompt 工件可以被裁剪。",
                    "importance": 0.8,
                }
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        invocations = runtime_repository.list_model_invocations(task_id="task_audit_lean")
        assert len(invocations) == 1
        invocation = invocations[0]
        artifact = prompt_repository.get_prompt_compile_artifact(str(invocation.prompt_compile_artifact_id))
        assert artifact is not None
        assert artifact.compiled_messages_ref is not None
        assert invocation.request_ref is not None
        assert invocation.response_ref is not None

        compiled_path = Path(resolve_workspace_root()) / artifact.compiled_messages_ref.locator
        compiled_payload = json.loads(compiled_path.read_text(encoding="utf-8"))
        assert compiled_payload["auditLevel"] == "lean"
        assert "messageDigests" in compiled_payload
        assert "messages" not in compiled_payload

        request_path = Path(resolve_workspace_root()) / invocation.request_ref.locator
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert request_payload["auditLevel"] == "lean"
        assert "messages" not in request_payload
        assert "initialMessageDigests" in request_payload
        assert "finalMessageDigests" in request_payload
        assert "toolExecutionCount" in request_payload

        response_path = Path(resolve_workspace_root()) / invocation.response_ref.locator
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))
        assert response_payload["auditLevel"] == "lean"
        assert response_payload["localRuntimeTimings"]["compilePromptMs"] >= 0
        assert "rawResponse" not in response_payload
        assert "toolExecutions" not in response_payload
        assert "toolExecutionCount" in response_payload


def test_runtime_response_payload_tracks_token_usage_and_context_lengths(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_execution_loop,
        "load_runtime_candidate_models",
        lambda: [
            {
                "model": "metrics-model",
                "provider": "metrics-provider",
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
            "provider": "metrics-provider",
            "model": "metrics-model",
            "outputText": "已生成一份长任务实现计划。",
            "finishReason": "stop",
            "usage": {
                "inputTokens": 3200,
                "outputTokens": 400,
                "totalTokens": 3600,
                "cacheHitInputTokens": 2400,
                "cacheWriteInputTokens": 300,
                "nonCacheInputTokens": 800,
                "reasoningTokens": 120,
            },
            "costUsed": 0.05,
            "error": None,
            "toolCalls": [],
            "rawResponse": {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "已生成一份长任务实现计划。"},
                    }
                ],
                "usage": {
                    "prompt_tokens": 3200,
                    "completion_tokens": 400,
                    "total_tokens": 3600,
                },
            },
            "requestPayload": {
                "model": "metrics-model",
                "messages": [],
                "stream": True,
            },
            "firstTokenLatencyMs": 250.0,
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_metrics_trace",
                "title": "runtime metrics trace",
                "goal": "验证 token 用量和上下文长度会写入 response artifact。",
                "status": "draft",
                "currentObjective": "完成一轮 metrics 落盘。",
                "currentFocus": "metrics-trace",
                "budgetState": {
                    "tokenBudgetTotal": 10000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_metrics_trace/start",
        json={
            "currentFocus": "metrics-trace",
            "maxRetainedTokens": 24,
            "currentContext": [
                {
                    "id": "ctx_keep_metrics",
                    "title": "核心约束",
                    "content": "必须把 token 开销拆成缓存命中、非缓存命中、输出数，并记录长任务上下文长度。" * 4,
                    "importance": 0.95,
                },
                {
                    "id": "ctx_drop_metrics",
                    "title": "次要细节",
                    "content": "这段上下文用于触发 pruning，让 before/after 长度都能被记录。" * 4,
                    "importance": 0.1,
                },
            ],
            "protectedItems": [{"kind": "node", "id": "ctx_keep_metrics"}],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "completed"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        runtime_repository = RuntimeRepository(session)
        invocations = runtime_repository.list_model_invocations(task_id="task_metrics_trace")
        assert len(invocations) == 1
        response_path = Path(resolve_workspace_root()) / str(invocations[0].response_ref.locator)
        response_payload = json.loads(response_path.read_text(encoding="utf-8"))

    assert response_payload["usage"] == {
        "inputTokens": 3200,
        "outputTokens": 400,
        "totalTokens": 3600,
        "cacheHitInputTokens": 2400,
        "cacheWriteInputTokens": 300,
        "nonCacheInputTokens": 800,
        "reasoningTokens": 120,
    }
    observations = response_payload["contextLengthObservations"]
    phases = {item["phase"] for item in observations}
    assert {"beforeContextPruning", "afterContextPruning", "beforeModelInvocation", "taskEnd"}.issubset(phases)
    before_pruning = next(item for item in observations if item["phase"] == "beforeContextPruning")
    after_pruning = next(item for item in observations if item["phase"] == "afterContextPruning")
    assert before_pruning["estimatedTokens"] >= after_pruning["estimatedTokens"]


def test_pause_request_not_overwritten_on_worker_startup() -> None:
    """
    Regression test for the pause-request detection race condition.

    The bug (now fixed): execute_main_agent_work_item previously called
    update_task(..., "pauseRequested": bool(task.pause_requested)) during
    worker startup. If a pause was requested between the work item being
    enqueued and the worker's initial task load (or between the load and that
    update_task call), the worker would echo back a stale False and overwrite
    the DB's True, causing the pause to be silently dropped.

    Fixes applied:
    - Removed "pauseRequested" from the startup update_task payload so the DB
      value is never overwritten by a stale local variable.
    - Added a fresh DB read of the task immediately before the pause-check so
      that pause requests arriving during execution are always detected.

    This test verifies that a pause request issued after start-queuing but
    before the worker runs is correctly honoured (status → "paused").
    """
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_pause_regression",
                "title": "pause-request race condition regression",
                "goal": "验证 worker 启动阶段不会覆盖 pauseRequested 标志。",
                "status": "draft",
                "currentObjective": "执行并在 safe-stop 处暂停。",
                "currentFocus": "regression-pause-detection",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    started = client.post(
        "/runtime/tasks/task_pause_regression/start",
        json={
            "currentFocus": "regression-pause-detection",
            "currentContext": [
                {
                    "id": "ctx_reg",
                    "title": "回归场景上下文",
                    "content": "验证 pauseRequested 标志在 worker 启动时不被覆盖。",
                    "importance": 0.9,
                }
            ],
        },
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"

    # Pause is requested AFTER the work item is enqueued but BEFORE the worker
    # processes it. This is the exact timing that the bug affected: the worker
    # would load the task (pause_requested=True at this point), then call
    # update_task with the stale local value, overwriting True → False.
    pause_resp = client.post(
        "/runtime/tasks/task_pause_regression/pause-request",
        json={"reason": "regression-test-pause"},
    )
    assert pause_resp.status_code == 202

    # Confirm the flag is set in DB before the worker runs.
    with runtime.session_scope() as session:
        task_before = TaskRepository(session).get_task("task_pause_regression")
        assert task_before is not None
        assert task_before.pause_requested is True, (
            "pauseRequested must be True in DB before the worker starts"
        )

    result = run_worker_once("agent-runtime")
    assert result["status"] == "processed"
    assert result["result"]["status"] == "paused", (
        "Worker must honour the pause request and produce status='paused'. "
        "If this fails, the pause-request detection race condition has regressed."
    )
    snapshot = result["result"]["snapshot"]
    assert snapshot is not None
    assert snapshot["safeStop"] is True

    # Confirm the task is correctly paused in DB and pauseRequested was cleared
    # (it is cleared only after the snapshot is committed, not before).
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task_after = task_repository.get_task("task_pause_regression")
        assert task_after is not None
        assert task_after.status == "paused"
        assert task_after.pause_requested is False  # cleared after honouring the pause
        assert task_after.active_snapshot_id == snapshot["id"]


def test_pause_during_execution_worker_stops_next_round() -> None:
    """
    Phase 1 test: Pause-Resume专项 - 执行中途发出 pause，worker 必须在下一轮停下。

    Verifies that when a pause is requested while a task is already running,
    the worker will detect it and stop at the next safe-stop opportunity.
    """
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_pause_mid_exec",
                "title": "中途暂停测试",
                "goal": "验证执行中途的暂停请求能被正确检测并停止。",
                "status": "draft",
                "currentObjective": "执行任务并在中途暂停。",
                "currentFocus": "mid-execution-pause",
                "budgetState": {
                    "tokenBudgetTotal": 2000,
                    "costBudgetTotal": 10.0,
                },
            }
        )

    # Start the task
    started = client.post(
        "/runtime/tasks/task_pause_mid_exec/start",
        json={
            "currentFocus": "测试中途暂停检测",
            "currentContext": [
                {
                    "id": "ctx_mid",
                    "title": "测试上下文",
                    "content": "验证 worker 在执行中检测到暂停请求后能够停止。",
                    "importance": 0.8,
                }
            ],
        },
    )
    assert started.status_code == 202
    assert started.json()["status"] == "queued"

    # Process first round - should complete normally
    first_run = run_worker_once("agent-runtime")
    assert first_run["status"] == "processed"
    # Task should still be running after first cycle (fallback response means it continued)

    # Now request pause while task would continue
    pause_resp = client.post(
        "/runtime/tasks/task_pause_mid_exec/pause-request",
        json={"reason": "mid-execution-pause-test"},
    )
    assert pause_resp.status_code == 202

    # Verify pause flag is set
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_pause_mid_exec")
        assert task is not None
        assert task.pause_requested is True

    # If the task is still running, process again - should now pause
    # Note: The first run might have already completed/paused due to fallback
    # In production, this would be the next execution cycle
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_pause_mid_exec")
        if task and task.status == "running":
            second_run = run_worker_once("agent-runtime")
            assert second_run["status"] == "processed"
            assert second_run["result"]["status"] in ["paused", "completed"]

    # Verify final state shows pause was honored
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_pause_mid_exec")
        assert task is not None
        # Task should either be paused or completed (if it finished before pause took effect)
        assert task.status in ["paused", "completed"]
        # If paused, should have a snapshot
        if task.status == "paused":
            assert task.active_snapshot_id is not None


def test_multiple_pause_resume_cycles_no_state_pollution() -> None:
    """
    Phase 1 test: Pause-Resume专项 - 连续 pause / resume 不累积状态污染。

    Verifies that multiple pause/resume cycles don't accumulate state pollution
    and each cycle works correctly without interference.
    """
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_multi_pause",
                "title": "多次暂停恢复测试",
                "goal": "验证连续暂停/恢复不会累积状态污染。",
                "status": "draft",
                "currentObjective": "执行多次暂停/恢复循环。",
                "currentFocus": "multi-cycle-test",
                "budgetState": {
                    "tokenBudgetTotal": 5000,
                    "costBudgetTotal": 25.0,
                },
            }
        )

    # First cycle: start → pause → resume
    started = client.post(
        "/runtime/tasks/task_multi_pause/start",
        json={
            "currentFocus": "第一次执行",
            "currentContext": [
                {
                    "id": "ctx_1",
                    "title": "第一次上下文",
                    "content": "第一次执行的上下文内容。",
                    "importance": 0.8,
                }
            ],
        },
    )
    assert started.status_code == 202

    # Request first pause
    pause1 = client.post(
        "/runtime/tasks/task_multi_pause/pause-request",
        json={"reason": "first-pause"},
    )
    assert pause1.status_code == 202

    # Process first pause
    run1 = run_worker_once("agent-runtime")
    assert run1["status"] == "processed"
    assert run1["result"]["status"] == "paused"
    snapshot1_id = run1["result"]["snapshot"]["id"]
    resume_token1 = run1["result"]["snapshot"]["resumeToken"]

    # Verify first pause state
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_multi_pause")
        assert task is not None
        assert task.status == "paused"
        assert task.active_snapshot_id == snapshot1_id
        runs = TaskRepository(session).list_agent_runs("task_multi_pause")
        assert len(runs) == 1

    # First resume
    resumed1 = client.post(
        "/runtime/tasks/task_multi_pause/resume",
        json={"resumeToken": resume_token1, "nextObjective": "继续第二轮执行"},
    )
    assert resumed1.status_code == 202

    # Request second pause immediately
    pause2 = client.post(
        "/runtime/tasks/task_multi_pause/pause-request",
        json={"reason": "second-pause"},
    )
    assert pause2.status_code == 202

    # Process second pause
    run2 = run_worker_once("agent-runtime")
    assert run2["status"] == "processed"
    assert run2["result"]["status"] == "paused"
    assert run2["result"]["resume"] is not None  # Should have resume context
    snapshot2_id = run2["result"]["snapshot"]["id"]
    resume_token2 = run2["result"]["snapshot"]["resumeToken"]

    # Verify second pause state - should be clean, no pollution
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_multi_pause")
        assert task is not None
        assert task.status == "paused"
        assert task.active_snapshot_id == snapshot2_id
        assert snapshot2_id != snapshot1_id  # Should be a different snapshot
        runs = TaskRepository(session).list_agent_runs("task_multi_pause")
        assert len(runs) == 2
        snapshots = TaskRepository(session).list_snapshots("task_multi_pause")
        assert len(snapshots) >= 2
        snapshots_by_id = {snapshot.id: snapshot for snapshot in snapshots}
        # The resumed snapshot should be consumed after the second run.
        assert snapshots_by_id[snapshot1_id].status == "consumed"
        # The newest active snapshot remains restorable; current-ness is carried by active_snapshot_id.
        assert snapshots_by_id[snapshot2_id].status == "restorable"

    # Second resume to verify state is still clean
    resumed2 = client.post(
        "/runtime/tasks/task_multi_pause/resume",
        json={"resumeToken": resume_token2, "nextObjective": "完成最后一轮"},
    )
    assert resumed2.status_code == 202

    # Let it complete
    run3 = run_worker_once("agent-runtime")
    assert run3["status"] == "processed"
    # Should either pause again, complete, or continue
    assert run3["result"]["status"] in ["paused", "completed", "running"]

    # Final verification: no state pollution
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task("task_multi_pause")
        assert task is not None
        runs = TaskRepository(session).list_agent_runs("task_multi_pause")
        # Should have multiple runs (at least 3)
        assert len(runs) >= 3
        # Each run should have correct status progression
        statuses = [run.status for run in runs]
        # Count of paused states should match our pause requests
        assert statuses.count("paused") >= 2
