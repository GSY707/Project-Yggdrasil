from __future__ import annotations

import pytest

from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.contracts import WorkTreeProtocol
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.runtime_kernel.fork_runtime import (
    ForkResultEnvelope,
    merge_fork_result_and_plan_next_batch,
    queue_fork_batch,
)
from yggdrasil_sdk.runtime_kernel.work_tree_graph import compute_parent_ready_set
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_worker.registry import run_worker_once


def _node(
    node_id: str,
    *,
    children: list[str] | None = None,
    depends_on: list[str] | None = None,
    priority: int = 100,
    status: str = "pending",
) -> dict[str, object]:
    return {
        "id": node_id,
        "title": node_id,
        "parentNodeId": None if node_id == "root" else "root",
        "questionsItAnswers": [node_id],
        "nodeText": node_id,
        "localGoal": node_id,
        "phase": "executing",
        "status": status,
        "childNodeIds": children or [],
        "dependsOn": depends_on or [],
        "priority": priority,
    }


def _work_tree() -> WorkTreeProtocol:
    return WorkTreeProtocol.model_validate(
        {
            "id": "wt-fork-merge",
            "rootNodeId": "root",
            "rootObjective": "验证 Fork result merge。",
            "status": "active",
            "currentNodeId": "root",
            "nodes": [
                _node("root", children=["child-a", "child-b", "child-c", "child-d"], status="in-progress"),
                _node("child-a", priority=1, status="in-progress"),
                _node("child-b", depends_on=["child-a"], priority=2),
                _node("child-c", priority=3),
                _node("child-d", depends_on=["child-a"], priority=4),
            ],
        }
    )


def _launch_work_tree() -> WorkTreeProtocol:
    payload = _work_tree().model_dump(by_alias=True, mode="json")
    for node in payload["nodes"]:
        if node["id"] == "child-a":
            node["status"] = "pending"
    return WorkTreeProtocol.model_validate(payload)


def _seed_task_and_runs(task_id: str, *, fork_node_id: str = "child-a") -> tuple[str, str]:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "title": task_id,
                "goal": "验证 Fork result merge 与 auto batch。",
                "status": "queued",
            }
        )
        parent = task_repository.create_agent_run(
            task_id,
            {
                "id": f"run_{task_id}_parent",
                "runType": "main",
                "status": "running",
            },
        )
        fork = task_repository.create_agent_run(
            task_id,
            {
                "id": f"run_{task_id}_fork",
                "parentRunId": parent.id,
                "runType": "fork",
                "status": "running",
                "forkRootRunId": parent.id,
                "forkDepth": 1,
                "assignedWorkTreeNodeId": fork_node_id,
                "parentContextAnchor": f"ctx-{task_id}",
                "forkGroupId": f"fork-group-{task_id}",
            },
        )
        return parent.id, fork.id


def test_fork_result_merge_auto_launches_next_ready_batch() -> None:
    task_id = "task_fork_merge_auto_batch"
    parent_run_id, fork_run_id = _seed_task_and_runs(task_id)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        result = merge_fork_result_and_plan_next_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent_run_id,
            parent_node_id="root",
            work_tree=_work_tree(),
            fork_run_id=fork_run_id,
            result_envelope={
                "assignedWorkTreeNodeId": "child-a",
                "status": "completed",
                "summary": "child-a produced the prerequisite evidence.",
                "evidenceRefs": [{"kind": "node", "id": "node-child-a-result"}],
                "planImpact": "none",
            },
            policy={"maxForks": 2},
        )

        child_a = next(node for node in result.work_tree.nodes if node.id == "child-a")
        assert child_a.status == "completed"
        assert child_a.execution_summary == "child-a produced the prerequisite evidence."
        assert child_a.produced_evidence_refs[0].id == "node-child-a-result"
        assert result.parent_replan_required is False
        assert result.next_batch is not None
        assert [item.assigned_work_tree_node_id for item in result.next_batch.queued_forks] == ["child-b", "child-c"]
        next_payload_tree = result.next_batch.queued_forks[0].work_item.payload["forkMergeContext"]["workTreeSnapshot"]
        next_child_a = next(node for node in next_payload_tree["nodes"] if node["id"] == "child-a")
        assert next_child_a["status"] == "completed"
        assert task_repository.get_agent_run(fork_run_id).status == "completed"


def test_fork_result_replan_blocks_auto_launch_and_keeps_pending_summary_only() -> None:
    task_id = "task_fork_merge_replan"
    parent_run_id, fork_run_id = _seed_task_and_runs(task_id)

    with pytest.raises(ValueError):
        ForkResultEnvelope.model_validate(
            {
                "assignedWorkTreeNodeId": "child-a",
                "summary": "needs graph change",
                "pendingInformationItems": [
                    {
                        "id": "pending-raw",
                        "targetNodeId": "child-b",
                        "category": "plan-impact",
                        "summary": "new dependency proposal",
                        "rawContent": "large raw child transcript must not be accepted",
                    }
                ],
            }
        )

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        result = merge_fork_result_and_plan_next_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent_run_id,
            parent_node_id="root",
            work_tree=_work_tree(),
            fork_run_id=fork_run_id,
            result_envelope={
                "assignedWorkTreeNodeId": "child-a",
                "status": "completed",
                "summary": "child-a found that parent must replan dependencies.",
                "planImpact": "requires-parent-replan",
                "pendingInformationItems": [
                    {
                        "id": "pending-replan",
                        "sourceNodeId": "child-a",
                        "targetNodeId": "child-b",
                        "category": "plan-impact",
                        "summary": "child-b should wait for a new dependency decision.",
                        "evidenceRefs": ["node-child-a-result"],
                    }
                ],
            },
            policy={"maxForks": 2},
        )

        assert result.parent_replan_required is True
        assert result.next_batch is None
        assert result.ready_set.parent_replan_required is True
        assert result.result_envelope.pending_information_items[0].summary == (
            "child-b should wait for a new dependency decision."
        )


def test_mixed_fork_outcome_only_launches_unblocked_ready_child() -> None:
    task_id = "task_fork_merge_mixed"
    parent_run_id, fork_run_id = _seed_task_and_runs(task_id)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        result = merge_fork_result_and_plan_next_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent_run_id,
            parent_node_id="root",
            work_tree=_work_tree(),
            fork_run_id=fork_run_id,
            result_envelope={
                "assignedWorkTreeNodeId": "child-a",
                "status": "failed",
                "summary": "child-a failed and dependent children must stay blocked.",
                "failureSummary": "missing upstream evidence",
                "planImpact": "none",
            },
            policy={"maxForks": 3},
        )

        child_a = next(node for node in result.work_tree.nodes if node.id == "child-a")
        assert child_a.status == "failed"
        assert child_a.failure_summary == "missing upstream evidence"
        assert result.next_batch is not None
        assert [item.assigned_work_tree_node_id for item in result.next_batch.queued_forks] == ["child-c"]
        blocked = {item.node_id: item.reason for item in result.ready_set.blocked_children}
        assert blocked["child-b"] == "dependency-not-completed"
        assert blocked["child-d"] == "dependency-not-completed"


def test_worker_fork_completion_merges_result_and_enqueues_next_batch(monkeypatch) -> None:
    task_id = "task_fork_worker_merge_auto"
    invoke_calls: list[dict[str, object]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        request_payload = kwargs.get("request") if isinstance(kwargs.get("request"), dict) else {}
        invoke_calls.append(request_payload)
        return {
            "assistantText": "# result\nchild-a finished.\n# evidence\nnode-child-a-result.\n# pending\nnone.\n# incomplete\nnone.",
            "invocation": {
                "id": "inv_fork_merge_worker",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "promptCompileArtifactId": "artifact_fork_merge_worker",
                "traceId": "trace_fork_merge_worker",
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
                "id": task_id,
                "title": "Fork worker merge",
                "goal": "验证真实 worker fork 完成后合并结果并启动下一批。",
                "status": "queued",
                "currentFocus": "parent-orchestration",
            }
        )
        parent = task_repository.create_agent_run(
            task_id,
            {
                "id": "run_fork_worker_merge_parent",
                "runType": "main",
                "status": "running",
            },
        )
        work_tree = _launch_work_tree()
        ready_set = compute_parent_ready_set(work_tree, "root", policy={"maxForks": 1})
        queue_fork_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent.id,
            ready_set=ready_set,
            policy={"maxForks": 1},
            work_tree=work_tree,
            parent_node_id="root",
        )

    processed = run_worker_once("agent-runtime")
    assert processed["status"] == "processed"
    result = processed["result"]
    assert result["status"] == "completed"
    fork_merge = result["forkMergeResult"]
    assert fork_merge["resultEnvelope"]["assignedWorkTreeNodeId"] == "child-a"
    assert fork_merge["workTree"]["pcMemo"] == "fork-result:child-a"
    child_a = next(node for node in fork_merge["workTree"]["nodes"] if node["id"] == "child-a")
    assert child_a["status"] == "completed"
    assert child_a["executionSummary"].startswith("# result")
    assert [item["assignedWorkTreeNodeId"] for item in fork_merge["nextBatch"]["queuedForks"]] == ["child-b"]
    next_payload_tree = fork_merge["nextBatch"]["queuedForks"][0]["workItem"]["payload"]["forkMergeContext"][
        "workTreeSnapshot"
    ]
    next_child_a = next(node for node in next_payload_tree["nodes"] if node["id"] == "child-a")
    assert next_child_a["status"] == "completed"
    assert [item["payload"]["assignedWorkTreeNodeId"] for item in result["forkQueuedWorkItems"]] == ["child-b"]
    assert result["executionStateAudit"]["forkResultMerged"] is True
    assert result["executionStateAudit"]["forkNextBatchQueued"] == 1
