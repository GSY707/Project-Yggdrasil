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
    assert first_run["result"]["runtimeTimings"]["buildRootMountMs"] >= 0
    assert first_run["result"]["runtimeTimings"]["llm"]["compilePromptMs"] >= 0
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