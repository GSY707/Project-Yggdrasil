from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow


def _seed_paused_task(task_id: str) -> str:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "title": f"{task_id} paused",
                "goal": "验证新暂停恢复链。",
                "status": "queued",
                "resumeMessage": "从 durable snapshot 继续。",
            }
        )
    pause_response = client.post(f"/runtime/tasks/{task_id}/pause", json={"reason": "seed-paused"})
    assert pause_response.status_code == 202
    snapshot_id = pause_response.json()["snapshot"]["id"]
    with runtime.session_scope() as session:
        task = TaskRepository(session).get_task(task_id)
        assert task is not None
        assert task.status == "paused"
        assert task.active_snapshot_id == snapshot_id
    return snapshot_id


def test_pause_queued_task_creates_pre_start_snapshot_and_cancels_work_item() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_pause_queued",
                "title": "queued pause",
                "goal": "queued 任务应立即暂停。",
                "status": "draft",
            }
        )

    started = client.post("/runtime/tasks/task_pause_queued/start", json={"currentFocus": "queued-pause"})
    assert started.status_code == 202
    assert started.json()["workItem"]["status"] == "queued"

    paused = client.post("/runtime/tasks/task_pause_queued/pause", json={"reason": "operator-pause-before-claim"})
    assert paused.status_code == 202
    payload = paused.json()
    assert payload["status"] == "paused"
    assert payload["snapshot"]["snapshotType"] == "pre-start"
    assert payload["snapshot"]["retentionClass"] == "active-paused"
    assert "resumeToken" not in payload["snapshot"]

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_pause_queued")
        snapshots = task_repository.list_snapshots("task_pause_queued")
        assert task is not None
        assert task.status == "paused"
        assert task.pause_requested is False
        assert task.active_snapshot_id == payload["snapshot"]["id"]
        assert snapshots[0].storage_manifest_ref is not None

    worker_result = run_worker_once("agent-runtime")
    assert worker_result["status"] == "empty"


def test_resume_creates_idempotent_attempt_and_keeps_active_snapshot() -> None:
    snapshot_id = _seed_paused_task("task_resume_attempt_idempotent")

    first = client.post("/runtime/tasks/task_resume_attempt_idempotent/resume", json={"resumeMessage": "继续。"})
    assert first.status_code == 202
    first_payload = first.json()
    assert first_payload["status"] == "resume-queued"
    assert first_payload["resumeAttempt"]["snapshotId"] == snapshot_id
    assert first_payload["task"]["status"] == "paused"
    assert first_payload["task"]["activeSnapshotId"] == snapshot_id
    assert first_payload["workItem"]["intent"] == "resume"

    second = client.post("/runtime/tasks/task_resume_attempt_idempotent/resume", json={})
    assert second.status_code == 202
    assert second.json()["resumeAttempt"]["id"] == first_payload["resumeAttempt"]["id"]
    assert second.json()["workItem"] is None

    with get_persistence_runtime().session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_resume_attempt_idempotent")
        snapshot = task_repository.get_snapshot(snapshot_id)
        attempt = task_repository.get_resume_attempt(first_payload["resumeAttempt"]["id"])
        assert task is not None
        assert snapshot is not None
        assert attempt is not None
        assert task.status == "paused"
        assert task.active_snapshot_id == snapshot_id
        assert snapshot.status == "restorable"
        assert attempt.status == "queued"


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
