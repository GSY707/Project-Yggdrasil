from __future__ import annotations

from typing import Any

from yggdrasil_sdk import (
    PromptAssetRepository,
    PromptProfileVersionRecord,
    TaskRepository,
    get_persistence_runtime,
    utc_now,
)
from yggdrasil_sdk.contracts import WorkTreeProtocol
from yggdrasil_sdk.persistence.constants import DEFAULT_PROJECT_ID
from yggdrasil_sdk.persistence.orm import TaskBranchORM
from yggdrasil_sdk.persistence.repositories import RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, relative_workspace_path, write_json
import yggdrasil_sdk.runtime_kernel.execution_loop as runtime_execution_loop
from yggdrasil_sdk.runtime_kernel.fork_runtime import queue_fork_batch
from yggdrasil_sdk.runtime_kernel.work_tree_graph import compute_parent_ready_set
from yggdrasil_worker.registry import run_worker_once
import sqlalchemy as sa


PROMPT_PROFILE_VERSION_ID = "prompt_profile_fork_runtime_harness"


def _seed_prompt_profile_version(prompt_repository: PromptAssetRepository) -> None:
    prompt_repository.upsert_prompt_profile_version(
        PromptProfileVersionRecord(
            id=PROMPT_PROFILE_VERSION_ID,
            promptProfileId="yggdrasil.fork-runtime-harness",
            name="Fork runtime harness",
            version="v1",
            runScope="any",
            body={"id": "yggdrasil.fork-runtime-harness", "version": "v1"},
            contentHash="prompt-profile-fork-runtime-harness-hash",
            createdAt=utc_now(),
        )
    )


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
            "id": "wt-fork-runtime-harness",
            "rootNodeId": "root",
            "rootObjective": "验证 Fork runtime harness 真实链路。",
            "status": "active",
            "currentNodeId": "root",
            "nodes": [
                _node("root", children=["child-a", "child-b"], status="in-progress"),
                _node("child-a", priority=1),
                _node("child-b", depends_on=["child-a"], priority=2),
            ],
        }
    )


def _persist_fake_invocation(
    session,
    *,
    task,
    run,
    route_decision,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    assistant_text: str,
    sequence: int,
) -> dict[str, Any]:
    runtime_repository = RuntimeRepository(session)
    prompt_repository = PromptAssetRepository(session)
    artifact_id = f"artifact_fork_runtime_harness_{sequence}_{run.id}"
    invocation_id = f"inv_fork_runtime_harness_{sequence}_{run.id}"
    prompt_dir = ensure_state_subdir("tests/fork-runtime-harness")
    compiled_messages_path = prompt_dir / f"{invocation_id}_messages.json"
    request_path = prompt_dir / f"{invocation_id}_request.json"
    response_path = prompt_dir / f"{invocation_id}_response.json"
    compiled_messages = [
        {"role": "system", "content": "deterministic fork runtime harness"},
        {
            "role": "user",
            "content": f"node={request['assignedWorkTreeNodeId']} pending={request.get('pendingInformationItems') or []}",
        },
    ]
    write_json(compiled_messages_path, compiled_messages)
    write_json(request_path, {"request": request, "rootMount": root_mount})
    write_json(response_path, {"assistantText": assistant_text})
    artifact = prompt_repository.create_prompt_compile_artifact(
        {
            "id": artifact_id,
            "projectId": DEFAULT_PROJECT_ID,
            "taskId": task.id,
            "agentRunId": run.id,
            "promptProfileVersionId": PROMPT_PROFILE_VERSION_ID,
            "runType": "fork",
            "taskType": "coding",
            "scenario": "fork-runtime-harness",
            "registeredTools": [],
            "bootSections": {"mode": "fork-runtime-harness"},
            "systemSections": {"forkNode": str(request.get("assignedWorkTreeNodeId"))},
            "userSections": {"pendingInformation": str(request.get("pendingInformationItems") or [])},
            "workTreeSnapshot": dict((request.get("forkMergeContext") or {}).get("workTreeSnapshot") or {}),
            "compiledMessagesRef": {
                "type": "file",
                "locator": relative_workspace_path(compiled_messages_path),
            },
            "contentHash": f"hash-{invocation_id}",
        }
    )
    invocation = runtime_repository.create_model_invocation(
        {
            "id": invocation_id,
            "projectId": DEFAULT_PROJECT_ID,
            "taskId": task.id,
            "agentRunId": run.id,
            "routeDecisionId": route_decision.id,
            "requestedModel": "deterministic-fork-harness",
            "requestedProvider": "fake",
            "resolvedModel": "deterministic-fork-harness",
            "resolvedProvider": "fake",
            "status": "completed",
            "traceId": f"trace-{invocation_id}",
            "promptCompileArtifactId": artifact.id,
            "requestRef": {
                "type": "file",
                "locator": relative_workspace_path(request_path),
            },
            "responseRef": {
                "type": "file",
                "locator": relative_workspace_path(response_path),
            },
            "inputTokensUsed": 32 + sequence,
            "outputTokensUsed": 16 + sequence,
            "costUsed": 0.0,
            "endedAt": utc_now(),
        }
    )
    return {
        "assistantText": assistant_text,
        "invocation": invocation.model_dump(by_alias=True, mode="json"),
        "usage": {
            "inputTokens": invocation.input_tokens_used,
            "outputTokens": invocation.output_tokens_used,
            "totalTokens": invocation.input_tokens_used + invocation.output_tokens_used,
        },
        "costUsed": invocation.cost_used,
        "toolExecutions": [],
        "timings": {"compilePromptMs": 0.0, "modelToolLoopMs": 0.0},
        "contextLengthObservations": [],
    }


def test_fork_runtime_harness_runs_two_worker_batches_with_artifacts_and_pending_flow(monkeypatch) -> None:
    task_id = "task_fork_runtime_harness"
    invoke_requests: list[dict[str, Any]] = []

    def _fake_invoke_runtime_completion(*args, **kwargs):  # type: ignore[no-untyped-def]
        session = args[0]
        request = kwargs["request"]
        invoke_requests.append(dict(request))
        node_id = str(request["assignedWorkTreeNodeId"])
        if node_id == "child-a":
            request["forkResultEnvelope"] = {
                "assignedWorkTreeNodeId": "child-a",
                "status": "completed",
                "summary": "child-a produced compact upstream evidence.",
                "evidenceRefs": [{"kind": "node", "id": "node-child-a-evidence"}],
                "planImpact": "none",
                "pendingInformationItems": [
                    {
                        "id": "pending-child-a-to-b",
                        "sourceNodeId": "child-a",
                        "targetNodeId": "child-b",
                        "category": "upstream-summary",
                        "summary": "child-b should use the compact child-a evidence summary.",
                        "evidenceRefs": ["node-child-a-evidence"],
                    }
                ],
            }
            assistant_text = "# result\nchild-a complete.\n# evidence\nnode-child-a-evidence.\n# pending\nchild-b summary.\n# incomplete\nnone."
        else:
            assert node_id == "child-b"
            pending_items = request.get("pendingInformationItems")
            assert isinstance(pending_items, list)
            assert pending_items[0]["summary"] == "child-b should use the compact child-a evidence summary."
            assert "rawContent" not in pending_items[0]
            request["forkResultEnvelope"] = {
                "assignedWorkTreeNodeId": "child-b",
                "status": "completed",
                "summary": "child-b consumed compact upstream evidence.",
                "evidenceRefs": [{"kind": "node", "id": "node-child-b-evidence"}],
                "planImpact": "none",
            }
            assistant_text = "# result\nchild-b complete.\n# evidence\nnode-child-b-evidence.\n# pending\nnone.\n# incomplete\nnone."
        return _persist_fake_invocation(
            session,
            task=kwargs["task"],
            run=kwargs["run"],
            route_decision=kwargs["route_decision"],
            request=request,
            root_mount=kwargs["root_mount"],
            assistant_text=assistant_text,
            sequence=len(invoke_requests),
        )

    monkeypatch.setattr(runtime_execution_loop, "invoke_runtime_completion", _fake_invoke_runtime_completion)

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        _seed_prompt_profile_version(PromptAssetRepository(session))
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "title": "Fork runtime harness",
                "goal": "验证 Fork runtime harness 两批真实 worker 链路。",
                "status": "queued",
                "currentFocus": "parent-orchestration",
            }
        )
        parent = task_repository.create_agent_run(
            task_id,
            {
                "id": "run_fork_runtime_harness_parent",
                "runType": "main",
                "status": "running",
            },
        )
        ready_set = compute_parent_ready_set(_work_tree(), "root", policy={"maxForks": 1})
        initial_batch = queue_fork_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent.id,
            ready_set=ready_set,
            policy={"maxForks": 1},
            parent_context_anchor="ctx-fork-runtime-harness",
            fork_group_id="fork-runtime-harness-group",
            work_tree=_work_tree(),
            parent_node_id="root",
        )
        first_work_item_id = initial_batch.queued_forks[0].work_item.id
        first_run_id = initial_batch.queued_forks[0].agent_run.id

    first_processed = run_worker_once("agent-runtime")
    assert first_processed["status"] == "processed"
    first_result = first_processed["result"]
    assert first_result["forkMergeResult"]["resultEnvelope"]["assignedWorkTreeNodeId"] == "child-a"
    assert [item["assignedWorkTreeNodeId"] for item in first_result["forkMergeResult"]["nextBatch"]["queuedForks"]] == [
        "child-b"
    ]
    second_work_item_id = first_result["forkQueuedWorkItems"][0]["id"]
    second_run_id = first_result["forkQueuedWorkItems"][0]["payload"]["agentRunId"]

    second_processed = run_worker_once("agent-runtime")
    assert second_processed["status"] == "processed"
    second_result = second_processed["result"]
    assert second_result["forkMergeResult"]["resultEnvelope"]["assignedWorkTreeNodeId"] == "child-b"
    assert second_result["forkMergeResult"]["nextBatch"] is None

    with runtime.session_scope() as session:
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        prompt_repository = PromptAssetRepository(session)
        first_work_item = task_repository.get_work_item(first_work_item_id)
        second_work_item = task_repository.get_work_item(second_work_item_id)
        first_run = task_repository.get_agent_run(first_run_id)
        second_run = task_repository.get_agent_run(second_run_id)
        task = task_repository.get_task(task_id)
        invocations = runtime_repository.list_model_invocations(task_id=task_id, limit=10)
        artifacts = prompt_repository.list_prompt_compile_artifacts(task_id=task_id, limit=10)
        task_branches = session.execute(sa.select(TaskBranchORM).where(TaskBranchORM.parent_task_id == task_id)).scalars().all()

        assert first_work_item is not None
        assert second_work_item is not None
        assert first_work_item.status == "completed"
        assert second_work_item.status == "completed"
        assert first_run is not None
        assert second_run is not None
        assert first_run.run_type == "fork"
        assert second_run.run_type == "fork"
        assert first_run.status == "completed"
        assert second_run.status == "completed"
        assert first_run.assigned_work_tree_node_id == "child-a"
        assert second_run.assigned_work_tree_node_id == "child-b"
        assert task is not None
        assert task.current_focus == "parent-orchestration"
        assert [record.id for record in task_repository.list_tasks(limit=10) if record.id == task_id] == [task_id]
        assert task_branches == []
        assert {invocation.agent_run_id for invocation in invocations} == {first_run_id, second_run_id}
        assert {artifact.agent_run_id for artifact in artifacts} == {first_run_id, second_run_id}
        assert {artifact.run_type for artifact in artifacts} == {"fork"}
        child_b_artifact = next(artifact for artifact in artifacts if artifact.agent_run_id == second_run_id)
        child_a_inherited = next(
            node for node in child_b_artifact.work_tree_snapshot["nodes"] if node["id"] == "child-a"
        )
        assert child_a_inherited["status"] == "completed"
        assert child_a_inherited["producedEvidenceRefs"][0]["id"] == "node-child-a-evidence"

    assert [request["assignedWorkTreeNodeId"] for request in invoke_requests] == ["child-a", "child-b"]
    assert invoke_requests[1]["pendingInformationItems"][0]["summary"] == (
        "child-b should use the compact child-a evidence summary."
    )
