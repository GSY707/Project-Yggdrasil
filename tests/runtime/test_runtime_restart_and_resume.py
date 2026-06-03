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
from yggdrasil_sdk.contracts import TaskSnapshotSummary
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.orm import RetrievalRequestORM
from yggdrasil_sdk.persistence.repositories import NodeRepository, RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel import post_task_mailbox_message
from yggdrasil_sdk.support import new_id, utc_now
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


client = TestClient(runtime_app)
pytestmark = pytest.mark.slow


def test_main_agent_start_without_active_work_enters_standby_without_running_model(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_start_standby",
                "title": "冷启动待机",
                "goal": "",
                "status": "draft",
            }
        )

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": (
                "# result\n已完成 standby 启动路径。\n"
                "# evidence\n无需真实模型即可完成。\n"
                "# pending\n无。\n"
                "# incomplete\n无。"
            ),
            "invocation": {
                "id": "inv_start_standby_1",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_start_standby",
                "traceId": "trace_start_standby",
            },
            "usage": {
                "inputTokens": 1,
                "outputTokens": 1,
                "totalTokens": 2,
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
    
    started = client.post("/runtime/tasks/task_start_standby/start", json={})
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] in {"continuing", "completed"}
    assert processed["result"]["rootMount"]["startupMode"] == "standby"
    assert len(invoke_calls) == 1
    assert invoke_calls[0]["takeoverProtocol"]["workTree"]["currentNodeId"].startswith("work-tree-node_")

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        task = task_repository.get_task("task_start_standby")
        runs = task_repository.list_agent_runs("task_start_standby")
        assert task is not None
        assert len(runs) == 1


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
    assert payload["workItem"]["command"] == "retry"
    assert payload["task"]["status"] == "queued"
    assert payload["task"]["budget"]["tokenBudgetTotal"] == 6000
    assert payload["task"]["budget"]["costBudgetTotal"] == 10.0


def test_mailbox_message_wakes_standby_task_and_is_consumed(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_mailbox_wake",
                "title": "邮箱唤醒待机任务",
                "goal": "",
                "status": "queued",
            }
        )

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": (
                "# result\n已消费 mailbox 消息并继续主循环。\n"
                "# evidence\nmailbox 消息已注入上下文并消费。\n"
                "# pending\n无。\n"
                "# incomplete\n无。"
            ),
            "invocation": {
                "id": "inv_mailbox_wake_1",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_mailbox_wake",
                "traceId": "trace_mailbox_wake",
            },
            "usage": {
                "inputTokens": 32,
                "outputTokens": 16,
                "totalTokens": 48,
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
    
    delivered = post_task_mailbox_message(
        "task_mailbox_wake",
        {
            "sender": {"type": "agent", "id": "subagent"},
            "messageKind": "subagent-completion",
            "subject": "Summarize child result",
            "body": "Child finished and needs parent synthesis.",
            "wakeOnMessage": True,
        },
    )
    assert delivered["mailboxState"]["pendingCount"] == 1
    assert delivered["wakeResult"]["status"] == "queued"

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] in {"continuing", "completed"}
    assert len(invoke_calls) == 1
    assert processed["result"]["rootMount"]["startupMode"] == "standby"

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task = task_repository.get_task("task_mailbox_wake")
        messages = runtime_repository.list_mailbox_messages(task_id="task_mailbox_wake", limit=10)
        assert task is not None
        assert task.status in {"queued", "running", "completed"}
        assert messages[0].status == "pending"


def test_resume_rejects_corrupted_snapshot_and_persists_reason() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": "task_corrupted_snapshot",
                "title": "损坏快照恢复拒绝",
                "goal": "验证损坏 snapshot 会拒绝恢复并保留错误原因。",
                "status": "paused",
                "resumeMessage": "尝试从损坏快照恢复。",
            }
        )
        run = task_repository.create_agent_run(
            task.id,
            {
                "id": "run_corrupted_snapshot",
                "status": "paused",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        snapshot = task_repository.create_snapshot(
            TaskSnapshotSummary(
                id="snapshot_corrupted_resume",
                appId=task.app_id,
                taskId=task.id,
                agentRunId=run.id,
                projectId=task.project_id,
                branchId=task.branch_id,
                snapshotType="restart",
                status="restorable",
                resumeToken=new_id("resume", task.id, run.id),
                contextRef={"type": "package-entry", "locator": f"runtime/tasks/{task.id}/snapshots/{run.id}/context"},
                rootMountRef={"type": "package-entry", "locator": f"runtime/tasks/{task.id}/snapshots/{run.id}/root-mount"},
                pendingWrites=[],
                pendingActions=[
                    {
                        "kind": "window-restart",
                        "sourceWindowIndex": 1,
                        "targetWindowIndex": 2,
                        "requestState": {
                            "currentNodeId": "node-corrupted",
                            "workingNodeAnnotation": "<Working_Node: node-corrupted>",
                        },
                        "checksum": "broken-checksum",
                    }
                ],
                resumeMessage="继续恢复损坏快照。",
                safeStopReason="context-window-restart",
                createdAt=utc_now(),
                safeToPause=True,
                blockers=[],
            )
        )
        task_repository.update_task(
            task.id,
            {
                "status": "paused",
                "activeSnapshotId": snapshot.id,
                "pauseRequested": False,
            },
        )

    resumed = client.post(
        "/runtime/tasks/task_corrupted_snapshot/resume",
        json={"resumeToken": snapshot.resume_token},
    )
    assert resumed.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] == "failed"
    assert "snapshot integrity check failed" in str(processed["result"]["detail"]).lower()

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        refreshed_task = task_repository.get_task("task_corrupted_snapshot")
        refreshed_snapshot = task_repository.get_snapshot("snapshot_corrupted_resume")
        assert refreshed_task is not None
        assert refreshed_task.status == "failed"
        assert refreshed_snapshot is not None
        assert refreshed_snapshot.status == "restorable"

def test_main_agent_runtime_retrieval_prefers_work_tree_focus_over_stale_current_focus(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        TaskRepository(session).create_task(
            {
                "id": "task_retrieval_work_tree_focus",
                "title": "retrieval 使用工作树焦点",
                "goal": "验证 stale currentFocus 不会压过 work tree 当前节点。",
                "status": "draft",
                "currentObjective": "继续执行当前工作树节点。",
                "currentFocus": "stale-ui-focus",
                "budgetState": {
                    "tokenBudgetTotal": 1200,
                    "costBudgetTotal": 5.0,
                },
            }
        )

    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(
            {
                "currentFocus": request_payload.get("currentFocus"),
                "currentNodeId": request_payload.get("currentNodeId"),
                "workingNodeAnnotation": request_payload.get("workingNodeAnnotation"),
                "retrievalWorkTreeNodeId": (
                    request_payload.get("memoryRetrievalState", {}).get("workTreeNodeId")
                    if isinstance(request_payload.get("memoryRetrievalState"), dict)
                    else None
                ),
                "retrievalSummary": (
                    request_payload.get("memoryRetrievalState", {}).get("summary")
                    if isinstance(request_payload.get("memoryRetrievalState"), dict)
                    else None
                ),
            }
        )
        return {
            "assistantText": (
                "# result\n已沿当前工作树节点继续执行。\n"
                "# evidence\n已完成。\n"
                "# pending\n无。\n"
                "# incomplete\n无。"
            ),
            "invocation": {
                "id": "inv_retrieval_work_tree_focus",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_retrieval_work_tree_focus",
                "traceId": "trace_retrieval_work_tree_focus",
            },
            "usage": {"inputTokens": 64, "outputTokens": 32, "totalTokens": 96},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)
    
    started = client.post(
        "/runtime/tasks/task_retrieval_work_tree_focus/start",
        json={
            "currentFocus": "stale-ui-focus",
            "currentObjective": "继续执行当前工作树节点。",
            "takeoverProtocol": {
                "id": "takeover_task_retrieval_work_tree_focus",
                "version": "0.2.0",
                "taskId": "task_retrieval_work_tree_focus",
                "taskType": "coding",
                "runType": "main",
                "currentPhase": "execute",
                "status": "executing",
                "objective": "继续执行当前工作树节点。",
                "objectiveSummary": "让 retrieval 与运行时指针使用 work tree。",
                "ambiguities": [],
                "constraints": [],
                "plan": [],
                "workTree": {
                    "version": "0.2.0",
                    "id": "work_tree_task_retrieval_work_tree_focus",
                    "taskId": "task_retrieval_work_tree_focus",
                    "rootNodeId": "root",
                    "rootObjective": "继续执行当前工作树节点。",
                    "status": "active",
                    "currentNodeId": "child-focus",
                    "loadedNodeIds": ["root", "child-focus"],
                    "activePathNodeIds": ["root", "child-focus"],
                    "pcMemo": "continue:child-focus",
                    "entropyBudgetRemaining": 8,
                    "versionCounter": 1,
                    "nodes": [
                        {
                            "id": "root",
                            "title": "根节点",
                            "parentNodeId": None,
                            "questionsItAnswers": ["最终交付是什么"],
                            "nodeText": "根节点。",
                            "localGoal": "根节点。",
                            "workingNodeAnnotation": "<Working_Node: root>",
                            "phase": "delivery",
                            "status": "in-progress",
                            "childNodeIds": ["child-focus"],
                            "detailLevel": 0,
                            "recoveryAnchor": "resume:root",
                        },
                        {
                            "id": "child-focus",
                            "title": "真实当前节点",
                            "parentNodeId": "root",
                            "questionsItAnswers": ["当前应执行什么"],
                            "nodeText": "真实当前工作节点。",
                            "localGoal": "继续执行真实当前工作节点。",
                            "workingNodeAnnotation": "<Working_Node: child-focus>",
                            "phase": "executing",
                            "status": "in-progress",
                            "childNodeIds": [],
                            "detailLevel": 1,
                            "recoveryAnchor": "resume:child-focus",
                        },
                    ],
                },
            },
        },
    )
    assert started.status_code == 202

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert processed["result"]["status"] in {"continuing", "completed"}
    assert len(invoke_calls) == 1
    assert invoke_calls[0]["currentFocus"] == "stale-ui-focus"
    assert invoke_calls[0]["workingNodeAnnotation"] is None
    assert invoke_calls[0]["retrievalWorkTreeNodeId"] is not None
    assert invoke_calls[0]["retrievalSummary"] is not None


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

    call_count = [0]

    def _fake_invoke_model(*args, **kwargs):  # type: ignore[no-untyped-def]
        call_count[0] += 1
        return {
            "mode": "fallback",
            "provider": None,
            "model": "fallback-synthetic",
            "outputText": (
                "# result\n已完成第 %d 轮 fallback 交付。\n"
                "# evidence\n已保留 pause/resume 运行时工件。\n"
                "# pending\n无。\n"
                "# incomplete\n无。"
            ) % call_count[0],
            "finishReason": "fallback",
            "usage": {
                "inputTokens": 64,
                "outputTokens": 24,
                "totalTokens": 88,
                "cacheHitInputTokens": 0,
                "cacheWriteInputTokens": 0,
                "nonCacheInputTokens": 64,
                "reasoningTokens": 0,
            },
            "costUsed": 0.0,
            "toolCalls": [],
            "error": "adapter-unavailable",
        }

    monkeypatch.setattr(yggdrasil_model_providers, "invoke_model", _fake_invoke_model)

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
        assert artifact.work_tree_snapshot is None
        assert artifact.takeover_protocol_snapshot is None
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
        assert request_payload["promptMetadata"].get("takeoverProtocol") is None
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
    assert first_run["result"]["takeoverProtocol"]["workTree"]["status"] in {"planned", "active", "verified", "completed"}
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
    assert second_run["result"]["status"] in {"continuing", "completed"}
    assert second_run["result"]["runtimeTimings"]["totalMs"] >= 0
    if second_run["result"]["status"] == "completed":
        assert second_run["result"]["resume"] is not None
        assert second_run["result"]["rehydration"] is not None
        assert any("Rehydrated" in summary for summary in second_run["result"]["rehydration"]["summaries"])
        assert second_run["result"]["rehydration"]["restoredState"]["requestUpdates"]["takeoverProtocol"]["workTree"]["currentNodeId"] is not None
    else:
        assert second_run["result"]["status"] == "continuing"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        node_repository = NodeRepository(session)
        task = task_repository.get_task("task_runtime")
        assert task is not None
        assert task.status in {"queued", "running", "paused", "completed"}
        assert task.active_snapshot_id is None
        runs = task_repository.list_agent_runs("task_runtime")
        assert len(runs) == 2
        assert {run.status for run in runs} <= {"paused", "completed", "queued", "running", "continuing"}
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
        artifact_1 = prompt_repository.get_prompt_compile_artifact(str(invocations[1].prompt_compile_artifact_id))
        assert artifact_1 is not None
        assert artifact_1.work_tree_snapshot is None
        assert artifact_1.takeover_protocol_snapshot is None

        artifact_2 = prompt_repository.get_prompt_compile_artifact(str(invocations[0].prompt_compile_artifact_id))
        assert artifact_2 is not None
        assert artifact_2.work_tree_snapshot is None
        assert artifact_2.takeover_protocol_snapshot is None
        execution_notes = [
            node
            for node in node_repository.list_nodes(branch_id=task.branch_id, limit=200)
            if node.node_type == "task" and node.parent_id == task.execution_root_node_id
        ]
        assert len(execution_notes) == 2
    assert second_run["result"]["takeoverProtocol"] is not None
    assert second_run["result"]["takeoverProtocol"]["workTree"]["status"] in {"active", "completed"}
    assert second_run["result"]["takeoverProtocolRef"] is not None


