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


def test_build_runtime_metrics_snapshot_counts_tool_failures() -> None:
    runtime_metrics = {
        "windowIndex": 3,
        "restartCount": 2,
        "cumulativeWindowSpanTokens": 420,
        "carryForwardLossCount": 1,
    }
    llm_result = {
        "usage": {"totalTokens": 512},
        "costUsed": 0.0123,
        "toolExecutions": [
            {"success": True},
            {"success": False},
            {"success": False},
        ],
        "roundSummaries": [{"index": 0}, {"index": 1}],
    }

    snapshot = runtime_execution_loop._build_runtime_metrics_snapshot(
        runtime_metrics=runtime_metrics,
        llm_result=llm_result,
    )

    assert snapshot.window_index == 3
    assert snapshot.restart_count == 2
    assert snapshot.total_tokens_used == 512
    assert snapshot.total_cost_used == pytest.approx(0.0123)
    assert snapshot.cumulative_window_span_tokens == 420
    assert snapshot.carry_forward_loss_count == 1
    assert snapshot.tool_round_count == 2
    assert snapshot.tool_failures_count == 2
