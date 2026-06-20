from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yggdrasil_sdk.contracts import WorkTreeNode, WorkTreeProtocol


ACTIVE_FORK_STATUSES = {"initializing", "mounting", "running", "waiting-tool"}


class PendingInformationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    source_node_id: str | None = Field(default=None, alias="sourceNodeId")
    target_node_id: str | None = Field(default=None, alias="targetNodeId")
    relation_id: str | None = Field(default=None, alias="relationId")
    relation_type: str | None = Field(default=None, alias="relationType")
    category: str = "context"
    summary: str
    evidence_refs: list[str] = Field(default_factory=list, alias="evidenceRefs")
    status: Literal["pending", "attached", "dismissed"] = "pending"


class ForkLaunchPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    max_forks: int = Field(default=3, alias="maxForks", ge=0)
    allow_recursive_fork: bool = Field(default=True, alias="allowRecursiveFork")
    auto_launch_policy: Literal["explicit-policy-gated", "manual", "disabled"] = Field(
        default="explicit-policy-gated",
        alias="autoLaunchPolicy",
    )
    ready_set_scope: Literal["direct-children-only"] = Field(default="direct-children-only", alias="readySetScope")
    pending_information_retention: Literal["summary-category-ref-only"] = Field(
        default="summary-category-ref-only",
        alias="pendingInformationRetention",
    )


class WorkTreeActiveRun(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    task_id: str | None = Field(default=None, alias="taskId")
    run_type: str = Field(default="main", alias="runType")
    status: str = "unknown"
    fork_root_run_id: str | None = Field(default=None, alias="forkRootRunId")
    parent_run_id: str | None = Field(default=None, alias="parentRunId")
    assigned_work_tree_node_id: str | None = Field(default=None, alias="assignedWorkTreeNodeId")


class WorkTreeReadySetInput(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid", arbitrary_types_allowed=True)

    work_tree: WorkTreeProtocol = Field(alias="workTree")
    parent_node_id: str = Field(alias="parentNodeId")
    active_runs: list[WorkTreeActiveRun] = Field(default_factory=list, alias="activeRuns")
    graph_state: dict[str, Any] = Field(default_factory=dict, alias="graphState")
    policy: ForkLaunchPolicy = Field(default_factory=ForkLaunchPolicy)


class WorkTreeReadyChild(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    title: str
    priority: int
    pending_information_items: list[PendingInformationItem] = Field(
        default_factory=list,
        alias="pendingInformationItems",
    )
    relation_ids: list[str] = Field(default_factory=list, alias="relationIds")


class WorkTreeBlockedChild(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    title: str
    priority: int
    reason: Literal[
        "dependency-not-completed",
        "already-active",
        "terminal",
        "not-pending",
        "missing-dependency",
    ]
    detail: str
    blocking_node_ids: list[str] = Field(default_factory=list, alias="blockingNodeIds")


class ForkLaunchCandidate(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    assigned_work_tree_node_id: str = Field(alias="assignedWorkTreeNodeId")
    priority: int
    pending_information_items: list[PendingInformationItem] = Field(
        default_factory=list,
        alias="pendingInformationItems",
    )


class WorkTreeReadySetResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    parent_node_id: str = Field(alias="parentNodeId")
    ready_children: list[WorkTreeReadyChild] = Field(default_factory=list, alias="readyChildren")
    blocked_children: list[WorkTreeBlockedChild] = Field(default_factory=list, alias="blockedChildren")
    fork_launch_candidates: list[ForkLaunchCandidate] = Field(default_factory=list, alias="forkLaunchCandidates")
    active_fork_count: int = Field(default=0, alias="activeForkCount")
    available_fork_slots: int = Field(default=0, alias="availableForkSlots")
    can_auto_launch: bool = Field(default=False, alias="canAutoLaunch")
    parent_replan_required: bool = Field(default=False, alias="parentReplanRequired")


class ForkBatchPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    launch_candidates: list[ForkLaunchCandidate] = Field(default_factory=list, alias="launchCandidates")
    waiting_candidates: list[ForkLaunchCandidate] = Field(default_factory=list, alias="waitingCandidates")
    active_fork_count: int = Field(default=0, alias="activeForkCount")
    available_fork_slots: int = Field(default=0, alias="availableForkSlots")
    reason: str = "ready-set"

    @model_validator(mode="after")
    def _slots_match_launch_count(self) -> "ForkBatchPlan":
        if len(self.launch_candidates) > self.available_fork_slots:
            raise ValueError("launchCandidates cannot exceed availableForkSlots")
        return self


def compute_parent_ready_set(
    work_tree: WorkTreeProtocol | Mapping[str, Any],
    parent_node_id: str,
    *,
    active_runs: Sequence[WorkTreeActiveRun | Mapping[str, Any]] | None = None,
    graph_state: Mapping[str, Any] | None = None,
    policy: ForkLaunchPolicy | Mapping[str, Any] | None = None,
) -> WorkTreeReadySetResult:
    request = WorkTreeReadySetInput(
        workTree=work_tree,
        parentNodeId=parent_node_id,
        activeRuns=list(active_runs or []),
        graphState=dict(graph_state or {}),
        policy=policy or ForkLaunchPolicy(),
    )
    node_by_id = {node.id: node for node in request.work_tree.nodes}
    parent = node_by_id.get(request.parent_node_id)
    if parent is None:
        raise ValueError(f"Unknown parent work tree node: {request.parent_node_id}")

    children = _direct_children(request.work_tree, parent)
    pending_by_target = _pending_information_by_target(request.graph_state)
    active_child_ids = {
        run.assigned_work_tree_node_id
        for run in request.active_runs
        if run.run_type == "fork"
        and run.status in ACTIVE_FORK_STATUSES
        and run.assigned_work_tree_node_id is not None
    }
    active_fork_count = sum(
        1 for run in request.active_runs if run.run_type == "fork" and run.status in ACTIVE_FORK_STATUSES
    )
    available_fork_slots = max(request.policy.max_forks - active_fork_count, 0)

    ready_children: list[WorkTreeReadyChild] = []
    blocked_children: list[WorkTreeBlockedChild] = []
    for child in sorted(children, key=lambda item: (item.priority, item.id)):
        blocked = _blocked_child(child, node_by_id=node_by_id, active_child_ids=active_child_ids)
        if blocked is not None:
            blocked_children.append(blocked)
            continue
        ready_children.append(
            WorkTreeReadyChild(
                nodeId=child.id,
                title=child.title,
                priority=child.priority,
                pendingInformationItems=pending_by_target.get(child.id, []),
                relationIds=list(child.relation_ids),
            )
        )

    fork_launch_candidates = [
        ForkLaunchCandidate(
            assignedWorkTreeNodeId=child.node_id,
            priority=child.priority,
            pendingInformationItems=child.pending_information_items,
        )
        for child in ready_children[:available_fork_slots]
    ]
    parent_replan_required = any(_requires_parent_replan(item) for items in pending_by_target.values() for item in items)
    return WorkTreeReadySetResult(
        parentNodeId=parent.id,
        readyChildren=ready_children,
        blockedChildren=blocked_children,
        forkLaunchCandidates=fork_launch_candidates,
        activeForkCount=active_fork_count,
        availableForkSlots=available_fork_slots,
        canAutoLaunch=(
            request.policy.auto_launch_policy == "explicit-policy-gated"
            and not parent_replan_required
            and bool(fork_launch_candidates)
        ),
        parentReplanRequired=parent_replan_required,
    )


def plan_fork_batch(
    ready_set: WorkTreeReadySetResult | Mapping[str, Any],
    policy: ForkLaunchPolicy | Mapping[str, Any] | None = None,
    *,
    active_fork_count: int | None = None,
) -> ForkBatchPlan:
    ready_set_model = WorkTreeReadySetResult.model_validate(ready_set)
    policy_model = ForkLaunchPolicy.model_validate(policy or ForkLaunchPolicy())
    effective_active_count = ready_set_model.active_fork_count if active_fork_count is None else active_fork_count
    available_slots = max(policy_model.max_forks - effective_active_count, 0)
    candidates = [
        ForkLaunchCandidate(
            assignedWorkTreeNodeId=child.node_id,
            priority=child.priority,
            pendingInformationItems=child.pending_information_items,
        )
        for child in ready_set_model.ready_children
    ]
    return ForkBatchPlan(
        launchCandidates=candidates[:available_slots],
        waitingCandidates=candidates[available_slots:],
        activeForkCount=effective_active_count,
        availableForkSlots=available_slots,
        reason="max-forks" if available_slots < len(candidates) else "ready-set",
    )


def _direct_children(work_tree: WorkTreeProtocol, parent: WorkTreeNode) -> list[WorkTreeNode]:
    node_by_id = {node.id: node for node in work_tree.nodes}
    ordered_ids = list(dict.fromkeys(parent.child_node_ids))
    children = [node_by_id[node_id] for node_id in ordered_ids if node_id in node_by_id]
    if children:
        return children
    return [node for node in work_tree.nodes if node.parent_node_id == parent.id]


def _pending_information_by_target(graph_state: Mapping[str, Any]) -> dict[str, list[PendingInformationItem]]:
    items = graph_state.get("pendingInformationItems") if isinstance(graph_state, Mapping) else None
    result: dict[str, list[PendingInformationItem]] = {}
    for raw_item in items or []:
        item = PendingInformationItem.model_validate(raw_item)
        if item.status != "pending" or item.target_node_id is None:
            continue
        result.setdefault(item.target_node_id, []).append(item)
    return result


def _blocked_child(
    child: WorkTreeNode,
    *,
    node_by_id: Mapping[str, WorkTreeNode],
    active_child_ids: set[str | None],
) -> WorkTreeBlockedChild | None:
    if child.id in active_child_ids:
        return WorkTreeBlockedChild(
            nodeId=child.id,
            title=child.title,
            priority=child.priority,
            reason="already-active",
            detail="Child already has an active fork assignment.",
        )
    if child.status in {"completed", "failed", "skipped"}:
        return WorkTreeBlockedChild(
            nodeId=child.id,
            title=child.title,
            priority=child.priority,
            reason="terminal",
            detail=f"Child is already terminal: {child.status}.",
        )
    if child.status != "pending":
        return WorkTreeBlockedChild(
            nodeId=child.id,
            title=child.title,
            priority=child.priority,
            reason="not-pending",
            detail=f"Child status is {child.status}, not pending.",
        )

    missing_dependencies = [node_id for node_id in child.depends_on if node_id not in node_by_id]
    if missing_dependencies:
        return WorkTreeBlockedChild(
            nodeId=child.id,
            title=child.title,
            priority=child.priority,
            reason="missing-dependency",
            detail="Child depends on missing work tree nodes.",
            blockingNodeIds=missing_dependencies,
        )

    unfinished_dependencies = [
        node_id for node_id in child.depends_on if node_by_id[node_id].status != "completed"
    ]
    if unfinished_dependencies:
        return WorkTreeBlockedChild(
            nodeId=child.id,
            title=child.title,
            priority=child.priority,
            reason="dependency-not-completed",
            detail="Child has hard dependsOn edges that are not completed.",
            blockingNodeIds=unfinished_dependencies,
        )
    return None


def _requires_parent_replan(item: PendingInformationItem) -> bool:
    return item.category in {"plan-impact", "dependency-change", "relation-change"} or item.relation_type in {
        "proposed-dependency-change",
        "proposed-relation-change",
    }
