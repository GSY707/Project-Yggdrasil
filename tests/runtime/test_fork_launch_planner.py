from __future__ import annotations

from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.contracts import WorkTreeProtocol
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_sdk.runtime_kernel.fork_runtime import queue_fork_batch
from yggdrasil_sdk.runtime_kernel.work_tree_graph import compute_parent_ready_set
from yggdrasil_worker.registry import run_worker_once


def _node(node_id: str, *, children: list[str] | None = None, priority: int = 100) -> dict[str, object]:
    return {
        "id": node_id,
        "title": node_id,
        "parentNodeId": None if node_id == "root" else "root",
        "questionsItAnswers": [node_id],
        "nodeText": node_id,
        "localGoal": node_id,
        "phase": "executing",
        "status": "pending",
        "childNodeIds": children or [],
        "priority": priority,
    }


def _work_tree() -> WorkTreeProtocol:
    return WorkTreeProtocol.model_validate(
        {
            "id": "wt-fork-launch",
            "rootNodeId": "root",
            "rootObjective": "验证 Fork batch 排队。",
            "status": "active",
            "currentNodeId": "root",
            "nodes": [
                _node("root", children=["child-a", "child-b", "child-c"]),
                _node("child-a", priority=1),
                _node("child-b", priority=2),
                _node("child-c", priority=3),
            ],
        }
    )


def test_queue_fork_batch_creates_fork_runs_and_main_work_items() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_fork_batch_queue",
                "title": "Fork batch queue",
                "goal": "验证 Fork batch planner 只排队可用槽位。",
                "status": "queued",
            }
        )
        parent = task_repository.create_agent_run(
            "task_fork_batch_queue",
            {
                "id": "run_fork_batch_parent",
                "runType": "main",
                "status": "running",
            },
        )
        existing_fork = task_repository.create_agent_run(
            "task_fork_batch_queue",
            {
                "id": "run_fork_batch_existing",
                "parentRunId": parent.id,
                "runType": "fork",
                "status": "running",
                "forkRootRunId": parent.id,
                "forkDepth": 1,
                "assignedWorkTreeNodeId": "existing-child",
                "parentContextAnchor": "ctx-existing",
                "forkGroupId": "fork-existing",
            },
        )
        ready_set = compute_parent_ready_set(
            _work_tree(),
            "root",
            active_runs=[
                {
                    "id": existing_fork.id,
                    "runType": "fork",
                    "status": existing_fork.status,
                    "assignedWorkTreeNodeId": existing_fork.assigned_work_tree_node_id,
                }
            ],
            policy={"maxForks": 3},
        )

        result = queue_fork_batch(
            task_repository=task_repository,
            task_id="task_fork_batch_queue",
            parent_run_id=parent.id,
            ready_set=ready_set,
            policy={"maxForks": 3},
            parent_context_anchor="ctx-parent-shared",
            fork_group_id="fork-group-batch-1",
        )

        assert result.active_fork_count == 1
        assert result.available_fork_slots == 2
        assert [item.assigned_work_tree_node_id for item in result.queued_forks] == ["child-a", "child-b"]
        assert [item.assigned_work_tree_node_id for item in result.batch_plan.waiting_candidates] == ["child-c"]
        assert {item.agent_run.parent_context_anchor for item in result.queued_forks} == {"ctx-parent-shared"}
        assert {item.agent_run.fork_group_id for item in result.queued_forks} == {"fork-group-batch-1"}
        assert {item.agent_run.run_type for item in result.queued_forks} == {"fork"}
        assert {item.work_item.activity for item in result.queued_forks} == {"core.agent.main.execute"}
        assert {item.work_item.intent for item in result.queued_forks} == {"fork"}

        first_payload = result.queued_forks[0].work_item.payload
        assert first_payload["runType"] == "fork"
        assert first_payload["payload"]["runType"] == "fork"
        assert first_payload["payload"]["parentContextAnchor"] == "ctx-parent-shared"
        assert first_payload["payload"]["assignedWorkTreeNodeId"] == "child-a"
        assert first_payload["payload"]["availableForkSlots"] == 2
        assert "subagent" not in first_payload["activity"]
        assert task_repository.count_active_fork_runs("task_fork_batch_queue", fork_root_run_id=parent.id) == 3


def test_worker_consumes_fork_work_item_with_child_view(monkeypatch) -> None:
    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": "Fork child finished.",
            "invocation": {
                "id": "inv_fork_worker_view",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_fork_worker_view",
                "traceId": "trace_fork_worker_view",
            },
            "usage": {"inputTokens": 32, "outputTokens": 16, "totalTokens": 48},
            "costUsed": 0.0,
            "toolExecutions": [],
            "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
            "contextLengthObservations": [],
        }

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_fork_worker_view",
                "title": "Fork worker view",
                "goal": "验证 Fork worker 运行视图。",
                "status": "queued",
                "currentFocus": "parent-orchestration",
            }
        )
        parent = task_repository.create_agent_run(
            "task_fork_worker_view",
            {
                "id": "run_fork_worker_parent",
                "runType": "main",
                "status": "running",
            },
        )
        ready_set = compute_parent_ready_set(_work_tree(), "root", policy={"maxForks": 1})
        result = queue_fork_batch(
            task_repository=task_repository,
            task_id="task_fork_worker_view",
            parent_run_id=parent.id,
            ready_set=ready_set,
            policy={"maxForks": 1},
            parent_context_anchor="ctx-worker-shared",
            fork_group_id="fork-worker-group",
        )
        fork_run_id = result.queued_forks[0].agent_run.id

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    assert invoke_calls
    request_payload = invoke_calls[0]
    assert request_payload["runType"] == "fork"
    assert request_payload["agentRunId"] == fork_run_id
    assert request_payload["assignedWorkTreeNodeId"] == "child-a"
    assert request_payload["currentNodeId"] == "child-a"
    assert request_payload["topFrameId"] == "child-a"
    assert request_payload["workingNodeAnnotation"] == "<Working_Node: child-a>"
    assert request_payload["parentContextAnchor"] == "ctx-worker-shared"
    assert request_payload["memoryRetrievalState"]["workTreeNodeId"] == "child-a"

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        fork_run = task_repository.get_agent_run(fork_run_id)
        task = task_repository.get_task("task_fork_worker_view")
        assert fork_run is not None
        assert fork_run.run_type == "fork"
        assert fork_run.parent_run_id == parent.id
        assert fork_run.fork_root_run_id == parent.id
        assert fork_run.assigned_work_tree_node_id == "child-a"
        assert fork_run.parent_context_anchor == "ctx-worker-shared"
        assert task is not None
        assert task.current_focus == "parent-orchestration"
