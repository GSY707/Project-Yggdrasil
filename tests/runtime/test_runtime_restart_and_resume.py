from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import sqlalchemy as sa

from yggdrasil_agent_runtime.app import app as runtime_app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime, resolve_workspace_root
from yggdrasil_sdk.persistence.orm import RetrievalRequestORM
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow


def test_main_agent_start_with_current_work_node_uses_task_state_loaded_startup_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_start_resume_node",
                "title": "热启动恢复当前节点",
                "goal": "验证 start 路径在已有工作节点但无真实恢复现场时，走任务态加载而不是无损恢复。",
                "status": "draft",
                "currentObjective": "继续执行 node-run。",
                "currentFocus": "node-run",
                "resumeMessage": "继续沿当前节点执行。",
                "budgetState": {
                    "tokenBudgetTotal": 1200,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": "已沿当前工作节点继续执行。",
            "invocation": {
                "id": "inv_start_resume_node_1",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_start_resume_node",
                "traceId": "trace_start_resume_node",
            },
            "usage": {
                "inputTokens": 48,
                "outputTokens": 20,
                "totalTokens": 68,
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
        "/runtime/tasks/task_start_resume_node/start",
        json={
            "currentObjective": "继续执行 node-run。",
            "currentFocus": "node-run",
            "currentNodeId": "node-run",
            "workingNodeAnnotation": "<Working_Node: node-run>",
            "pcMemo": "continue:node-run",
            "takeoverProtocol": {
                "id": "takeover_start_resume_node",
                "version": "0.1.0",
                "taskId": "task_start_resume_node",
                "taskType": "coding",
                "runType": "main",
                "currentPhase": "execute",
                "status": "prepared",
                "objective": "继续执行 node-run。",
                "objectiveSummary": "继续执行 node-run。",
                "ambiguities": [],
                "constraints": [],
                "plan": [],
                "workTree": {
                    "version": "0.1.0",
                    "rootObjective": "继续执行 node-run。",
                    "status": "active",
                    "currentNodeId": "node-run",
                    "nodes": [
                        {
                            "id": "node-run",
                            "title": "继续执行 node-run",
                            "phase": "executing",
                            "status": "in-progress",
                            "planStepIds": [],
                            "constraintIds": [],
                            "dependsOn": [],
                            "expectedEvidence": [],
                            "recoveryAnchor": "resume:node-run",
                        }
                    ],
                    "recoveryAnchor": "resume:node-run",
                    "entropyBudgetRemaining": 9,
                },
                "deliverySections": [],
                "verificationItems": [],
                "metrics": {
                    "planQualityScore0_100": 91.0,
                    "reworkCount": 0,
                    "reworkRate": 0.0,
                    "clarificationNeeded": False,
                    "deliveryCompletenessScore0_100": 0.0,
                    "verificationPassRate": 0.0,
                },
                "appliedModules": ["task-takeover"],
                "hookTrace": [],
            },
            "currentContext": [
                {
                    "id": "ctx_resume_node",
                    "title": "继续当前节点",
                    "content": "当前任务已经有稳定工作节点，应直接恢复而不是重建初始计划。",
                    "importance": 0.9,
                }
            ],
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert len(invoke_calls) == 1, processed["result"].get("detail")
    assert invoke_calls[0]["currentNodeId"] == "node-run"
    assert invoke_calls[0]["workingNodeAnnotation"] == "<Working_Node: node-run>"
    assert invoke_calls[0]["memoryRetrievalState"]["workTreeNodeId"] == "node-run"

    with runtime.session_scope() as session:
        retrieval_requests = session.execute(sa.select(RetrievalRequestORM).order_by(RetrievalRequestORM.created_at.asc())).scalars().all()
        assert any(record.work_tree_node_id == "node-run" for record in retrieval_requests)


def test_runtime_retry_failed_task_requeues_with_updated_budget() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_runtime_retry",
                "title": "失败重试",
                "goal": "验证 runtime retry 控制入口。",
                "status": "failed",
                "resumeMessage": "追加预算后继续。",
                "budgetState": {
                    "tokenBudgetTotal": 1000,
                    "tokenBudgetUsed": 900,
                    "costBudgetTotal": 2.0,
                    "costBudgetUsed": 1.5,
                },
            }
        )

    retry_response = client.post(
        "/runtime/tasks/task_runtime_retry/retry",
        json={
            "reason": "manual-retry-after-top-up",
            "budgetState": {
                "tokenBudgetTotal": 6000,
                "tokenBudgetUsed": 900,
                "costBudgetTotal": 10.0,
                "costBudgetUsed": 1.5,
            },
        },
    )
    assert retry_response.status_code == 202
    payload = retry_response.json()
    assert payload["status"] == "queued"
    assert payload["workItem"]["intent"] == "retry"
    assert payload["workItem"]["payload"]["command"] == "retry"
    assert payload["task"]["status"] == "queued"
    assert payload["task"]["budget"]["tokenBudgetTotal"] == 6000
    assert payload["task"]["budget"]["costBudgetTotal"] == 10.0


def test_durable_resume_blocks_on_corrupted_manifest() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_corrupt_manifest_resume",
                "title": "durable manifest corrupt",
                "goal": "损坏 manifest 必须阻断恢复。",
                "status": "queued",
                "resumeMessage": "从 durable snapshot 恢复。",
            }
        )

    paused = client.post("/runtime/tasks/task_corrupt_manifest_resume/pause", json={"reason": "seed-corrupt-manifest"})
    assert paused.status_code == 202
    snapshot = paused.json()["snapshot"]
    manifest_locator = snapshot["storageManifestRef"]["locator"]
    manifest_path = Path(resolve_workspace_root()) / manifest_locator
    manifest_path.write_text('{"version":"broken"}', encoding="utf-8")

    resumed = client.post("/runtime/tasks/task_corrupt_manifest_resume/resume", json={})
    assert resumed.status_code == 202
    assert resumed.json()["status"] == "resume-queued"

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "blocked"
    assert processed["result"]["blockerCode"] == "manifest-invalid"

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_corrupt_manifest_resume")
        refreshed_snapshot = task_repository.get_snapshot(snapshot["id"])
        attempt = task_repository.get_active_resume_attempt("task_corrupt_manifest_resume")
        assert task is not None
        assert refreshed_snapshot is not None
        assert attempt is not None
        assert task.status == "resume-blocked"
        assert task.active_snapshot_id == snapshot["id"]
        assert refreshed_snapshot.status == "blocked"
        assert attempt.status == "blocked"

