import json
from pathlib import Path

from fastapi.testclient import TestClient

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_agent_runtime.runtime import build_root_mount_package, prepare_pause_snapshot
from yggdrasil_context_pruning.plugin import ContextPruningModule
from yggdrasil_sdk import PromptAssetRepository, TaskRepository, get_persistence_runtime, resolve_workspace_root
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)


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
    snapshot = first_run["result"]["snapshot"]

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
        assert invocations[0].request_ref is not None
        assert invocations[0].response_ref is not None
        request_path = Path(resolve_workspace_root()) / invocations[0].request_ref.locator
        request_payload = json.loads(request_path.read_text(encoding="utf-8"))
        assert request_payload["appId"] == DEFAULT_APP_ID
        assert request_payload["promptCompileArtifactId"] == invocations[0].prompt_compile_artifact_id
        assert request_payload["promptMetadata"]["promptProfileId"] == "yggdrasil.main-agent"
        assert request_payload["promptMetadata"]["seedTemplateId"] == "yggdrasil.seed.generic.default"
        assert request_payload["promptMetadata"]["runType"] == "main"
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 1

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
    assert second_run["result"]["resume"] is not None
    assert second_run["result"]["rehydration"] is not None
    assert any("Rehydrated" in summary for summary in second_run["result"]["rehydration"]["summaries"])

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
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
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 2


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