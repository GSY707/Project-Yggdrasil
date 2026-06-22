from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from yggdrasil_sdk.contracts import EntityRef, WorkTreeProtocol
from yggdrasil_sdk.domain import AgentRunRecord, RuntimeWorkItemRecord
from yggdrasil_sdk.persistence.repositories import TaskRepository
from yggdrasil_sdk.support import new_id, normalize_excerpt, utc_now

from ._common import AGENT_RUNTIME_QUEUE
from .work_tree_graph import (
    ForkBatchPlan,
    ForkLaunchPolicy,
    PendingInformationItem,
    WorkTreeReadySetResult,
    compute_parent_ready_set,
    plan_fork_batch,
)


class QueuedForkRun(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    agent_run: AgentRunRecord = Field(alias="agentRun")
    work_item: RuntimeWorkItemRecord = Field(alias="workItem")
    assigned_work_tree_node_id: str = Field(alias="assignedWorkTreeNodeId")


class ForkRuntimeBatchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    fork_group_id: str = Field(alias="forkGroupId")
    parent_context_anchor: str = Field(alias="parentContextAnchor")
    fork_root_run_id: str = Field(alias="forkRootRunId")
    fork_depth: int = Field(alias="forkDepth")
    active_fork_count: int = Field(alias="activeForkCount")
    available_fork_slots: int = Field(alias="availableForkSlots")
    queued_forks: list[QueuedForkRun] = Field(default_factory=list, alias="queuedForks")
    batch_plan: ForkBatchPlan = Field(alias="batchPlan")


class ForkResultEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    assigned_work_tree_node_id: str = Field(alias="assignedWorkTreeNodeId")
    status: Literal["completed", "failed"] = "completed"
    summary: str
    evidence_refs: list[EntityRef] = Field(default_factory=list, alias="evidenceRefs")
    failure_summary: str | None = Field(default=None, alias="failureSummary")
    plan_impact: Literal["none", "requires-parent-replan"] = Field(default="none", alias="planImpact")
    proposed_dependency_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="proposedDependencyChanges",
    )
    proposed_relation_changes: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="proposedRelationChanges",
    )
    pending_information_items: list[PendingInformationItem] = Field(
        default_factory=list,
        alias="pendingInformationItems",
    )


class ForkMergeAndBatchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    result_envelope: ForkResultEnvelope = Field(alias="resultEnvelope")
    work_tree: WorkTreeProtocol = Field(alias="workTree")
    ready_set: WorkTreeReadySetResult = Field(alias="readySet")
    next_batch: ForkRuntimeBatchResult | None = Field(default=None, alias="nextBatch")
    parent_replan_required: bool = Field(default=False, alias="parentReplanRequired")


def queue_fork_batch(
    *,
    task_repository: TaskRepository,
    task_id: str,
    parent_run_id: str,
    ready_set: WorkTreeReadySetResult | dict[str, Any],
    policy: ForkLaunchPolicy | dict[str, Any] | None = None,
    fork_root_run_id: str | None = None,
    fork_depth: int = 1,
    parent_context_anchor: str | None = None,
    fork_group_id: str | None = None,
    queue: str = AGENT_RUNTIME_QUEUE,
    selected_model: str | None = None,
    selected_provider: str | None = None,
    work_tree: WorkTreeProtocol | dict[str, Any] | None = None,
    parent_node_id: str | None = None,
    auto_launch_next_batch: bool = True,
) -> ForkRuntimeBatchResult:
    ready_set_model = WorkTreeReadySetResult.model_validate(ready_set)
    policy_model = ForkLaunchPolicy.model_validate(policy or ForkLaunchPolicy())
    batch_plan = plan_fork_batch(
        ready_set_model,
        policy_model,
        active_fork_count=ready_set_model.active_fork_count,
    )
    effective_fork_root_run_id = fork_root_run_id or parent_run_id
    effective_fork_depth = max(int(fork_depth), 1)
    effective_parent_context_anchor = parent_context_anchor or new_id(
        "fork-context-anchor",
        task_id,
        parent_run_id,
        utc_now().isoformat(),
    )
    effective_fork_group_id = fork_group_id or new_id(
        "fork-group",
        task_id,
        parent_run_id,
        effective_parent_context_anchor,
    )

    queued_forks: list[QueuedForkRun] = []
    for candidate in batch_plan.launch_candidates:
        assigned_node_id = candidate.assigned_work_tree_node_id
        run = task_repository.create_agent_run(
            task_id,
            {
                "parentRunId": parent_run_id,
                "runType": "fork",
                "status": "initializing",
                "forkRootRunId": effective_fork_root_run_id,
                "forkDepth": effective_fork_depth,
                "assignedWorkTreeNodeId": assigned_node_id,
                "parentContextAnchor": effective_parent_context_anchor,
                "forkGroupId": effective_fork_group_id,
                "selectedModel": selected_model or "gpt-5.4",
                "selectedProvider": selected_provider,
            },
        )
        work_item_payload = _fork_work_item_payload(
            task_id=task_id,
            parent_run_id=parent_run_id,
            run=run,
            assigned_work_tree_node_id=assigned_node_id,
            fork_root_run_id=effective_fork_root_run_id,
            fork_depth=effective_fork_depth,
            parent_context_anchor=effective_parent_context_anchor,
            fork_group_id=effective_fork_group_id,
            active_fork_count=batch_plan.active_fork_count,
            available_fork_slots=batch_plan.available_fork_slots,
            pending_information_items=[
                item.model_dump(by_alias=True, mode="json") for item in candidate.pending_information_items
            ],
            work_tree=work_tree,
            parent_node_id=parent_node_id or ready_set_model.parent_node_id,
            policy=policy_model,
            auto_launch_next_batch=auto_launch_next_batch,
        )
        work_item = task_repository.create_work_item(queue, work_item_payload)
        queued_forks.append(
            QueuedForkRun(
                agentRun=run,
                workItem=work_item,
                assignedWorkTreeNodeId=assigned_node_id,
            )
        )

    return ForkRuntimeBatchResult(
        forkGroupId=effective_fork_group_id,
        parentContextAnchor=effective_parent_context_anchor,
        forkRootRunId=effective_fork_root_run_id,
        forkDepth=effective_fork_depth,
        activeForkCount=batch_plan.active_fork_count,
        availableForkSlots=batch_plan.available_fork_slots,
        queuedForks=queued_forks,
        batchPlan=batch_plan,
    )


def merge_fork_result_and_plan_next_batch(
    *,
    task_repository: TaskRepository,
    task_id: str,
    parent_run_id: str,
    parent_node_id: str,
    work_tree: WorkTreeProtocol | dict[str, Any],
    result_envelope: ForkResultEnvelope | dict[str, Any],
    policy: ForkLaunchPolicy | dict[str, Any] | None = None,
    fork_run_id: str | None = None,
    fork_root_run_id: str | None = None,
    fork_depth: int = 1,
    auto_launch: bool = True,
) -> ForkMergeAndBatchResult:
    envelope = ForkResultEnvelope.model_validate(result_envelope)
    policy_model = ForkLaunchPolicy.model_validate(policy or ForkLaunchPolicy())
    merged_work_tree = _merge_fork_result_into_work_tree(
        WorkTreeProtocol.model_validate(work_tree),
        envelope,
        fork_run_id=fork_run_id,
    )

    if fork_run_id is not None:
        task_repository.update_agent_run(
            fork_run_id,
            {
                "status": envelope.status,
                "assignedWorkTreeNodeId": envelope.assigned_work_tree_node_id,
                "forkRootRunId": fork_root_run_id or parent_run_id,
                "forkDepth": fork_depth,
            },
        )

    active_runs = [
        run.model_dump(by_alias=True, mode="json")
        for run in task_repository.list_agent_runs(task_id)
    ]
    graph_state = {
        "pendingInformationItems": [
            item.model_dump(by_alias=True, mode="json")
            for item in envelope.pending_information_items
        ]
    }
    ready_set = compute_parent_ready_set(
        merged_work_tree,
        parent_node_id,
        active_runs=active_runs,
        graph_state=graph_state,
        policy=policy_model,
    )
    parent_replan_required = envelope.plan_impact == "requires-parent-replan" or ready_set.parent_replan_required
    next_batch = None
    if auto_launch and envelope.plan_impact == "none" and ready_set.can_auto_launch:
        next_batch = queue_fork_batch(
            task_repository=task_repository,
            task_id=task_id,
            parent_run_id=parent_run_id,
            ready_set=ready_set,
            policy=policy_model,
            fork_root_run_id=fork_root_run_id or parent_run_id,
            fork_depth=fork_depth,
            work_tree=merged_work_tree,
            parent_node_id=parent_node_id,
            auto_launch_next_batch=auto_launch,
        )

    return ForkMergeAndBatchResult(
        resultEnvelope=envelope,
        workTree=merged_work_tree,
        readySet=ready_set,
        nextBatch=next_batch,
        parentReplanRequired=parent_replan_required,
    )


def _fork_work_item_payload(
    *,
    task_id: str,
    parent_run_id: str,
    run: AgentRunRecord,
    assigned_work_tree_node_id: str,
    fork_root_run_id: str,
    fork_depth: int,
    parent_context_anchor: str,
    fork_group_id: str,
    active_fork_count: int,
    available_fork_slots: int,
    pending_information_items: list[dict[str, Any]],
    work_tree: WorkTreeProtocol | dict[str, Any] | None,
    parent_node_id: str,
    policy: ForkLaunchPolicy,
    auto_launch_next_batch: bool,
) -> dict[str, Any]:
    work_tree_snapshot = (
        WorkTreeProtocol.model_validate(work_tree).model_dump(by_alias=True, mode="json")
        if work_tree is not None
        else None
    )
    fork_request = {
        "runType": "fork",
        "agentRunId": run.id,
        "parentRunId": parent_run_id,
        "forkRootRunId": fork_root_run_id,
        "forkDepth": fork_depth,
        "assignedWorkTreeNodeId": assigned_work_tree_node_id,
        "workTreeNodeId": assigned_work_tree_node_id,
        "currentNodeId": assigned_work_tree_node_id,
        "topFrameId": assigned_work_tree_node_id,
        "workingNodeAnnotation": f"<Working_Node: {assigned_work_tree_node_id}>",
        "memoryRetrievalState": {"workTreeNodeId": assigned_work_tree_node_id},
        "parentContextAnchor": parent_context_anchor,
        "forkGroupId": fork_group_id,
        "activeForkCount": active_fork_count,
        "availableForkSlots": available_fork_slots,
        "pendingInformationItems": pending_information_items,
        "forkMergeContext": {
            "parentNodeId": parent_node_id,
            "workTreeSnapshot": work_tree_snapshot,
            "policy": policy.model_dump(by_alias=True, mode="json"),
            "autoLaunchNextBatch": auto_launch_next_batch,
        },
    }
    return {
        "activity": "core.agent.main.execute",
        "taskId": task_id,
        "command": "start",
        "intent": "fork",
        "parentRunId": parent_run_id,
        "runType": "fork",
        "agentRunId": run.id,
        "forkRootRunId": fork_root_run_id,
        "forkDepth": fork_depth,
        "assignedWorkTreeNodeId": assigned_work_tree_node_id,
        "workTreeNodeId": assigned_work_tree_node_id,
        "currentNodeId": assigned_work_tree_node_id,
        "topFrameId": assigned_work_tree_node_id,
        "workingNodeAnnotation": f"<Working_Node: {assigned_work_tree_node_id}>",
        "parentContextAnchor": parent_context_anchor,
        "forkGroupId": fork_group_id,
        "activeForkCount": active_fork_count,
        "availableForkSlots": available_fork_slots,
        "forkMergeContext": fork_request["forkMergeContext"],
        "payload": fork_request,
    }


def _merge_fork_result_into_work_tree(
    work_tree: WorkTreeProtocol,
    envelope: ForkResultEnvelope,
    *,
    fork_run_id: str | None,
) -> WorkTreeProtocol:
    now = utc_now()
    updated_nodes: list[dict[str, Any]] = []
    found = False
    for node in work_tree.nodes:
        payload = node.model_dump(by_alias=True, mode="json")
        if node.id == envelope.assigned_work_tree_node_id:
            found = True
            payload["status"] = envelope.status
            payload["phase"] = "delivery" if envelope.status == "completed" else "recovering"
            payload["executionSummary"] = normalize_excerpt(envelope.summary, 240)
            payload["failureSummary"] = (
                normalize_excerpt(envelope.failure_summary or envelope.summary, 240)
                if envelope.status == "failed"
                else None
            )
            payload["producedEvidenceRefs"] = [
                ref.model_dump(mode="json") for ref in envelope.evidence_refs
            ]
            if fork_run_id is not None:
                payload["assignedAgentRunId"] = fork_run_id
            payload["updatedAt"] = now
        updated_nodes.append(payload)
    if not found:
        raise ValueError(f"Unknown assigned work tree node: {envelope.assigned_work_tree_node_id}")
    return WorkTreeProtocol.model_validate(
        {
            **work_tree.model_dump(by_alias=True, mode="json"),
            "nodes": updated_nodes,
            "pcMemo": normalize_excerpt(f"fork-result:{envelope.assigned_work_tree_node_id}", 160),
            "updatedAt": now,
        }
    )
