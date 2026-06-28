from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from yggdrasil_sdk.contracts import WorkTreeNode, WorkTreeProtocol


ACTIVE_FORK_STATUSES = {"initializing", "mounting", "running", "waiting-tool"}
TERMINAL_WORK_TREE_NODE_STATUSES = {"completed", "failed", "skipped"}

ResolutionAction = Literal["refine", "work", "merge", "deliver", "block"]
FrontierStatus = Literal["open", "resolved", "accepted-risk"]
FrontierAxis = Literal[
    "unknown",
    "risk",
    "deliverable",
    "dependency",
    "verification",
    "cost",
    "conflict",
    "failure",
    "plan-churn",
    "reliability",
    "durability",
    "transaction",
    "planning",
    "merge",
    "hygiene",
    "evaluation",
    "observability",
]

LONG_RUN_CORE_GAP_FRONTIER_SPECS: tuple[tuple[str, FrontierAxis, str, float], ...] = (
    (
        "queue-reliability",
        "reliability",
        "Worker queue needs ack, visibility timeout, reclaim and idempotent work item semantics.",
        0.95,
    ),
    (
        "durable-snapshot",
        "durability",
        "Resume state must be durable; Redis TTL package entries cannot be the recovery authority.",
        0.95,
    ),
    (
        "transactional-node",
        "transaction",
        "Work tree node execution needs preconditions, postconditions, version checks and idempotency keys.",
        0.9,
    ),
    (
        "plan-lifecycle",
        "planning",
        "Plan nodes need lifecycle, supersession and stale-plan detection instead of one-shot planning.",
        0.85,
    ),
    (
        "typed-merge",
        "merge",
        "Fork and child results need typed merge envelopes, not only natural-language summaries.",
        0.85,
    ),
    (
        "semantic-gc",
        "hygiene",
        "Long work trees need semantic garbage collection for obsolete plans, summaries and transcripts.",
        0.8,
    ),
    (
        "long-run-eval",
        "evaluation",
        "Long and ultra-long tasks need explicit deterministic and live gates rather than smoke evidence.",
        0.9,
    ),
    (
        "observability-replay",
        "observability",
        "Ultra-long runs need replayable traces to locate the first bad plan, summary or tool transition.",
        0.85,
    ),
)


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


class FrontierItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    node_id: str | None = Field(default=None, alias="nodeId")
    axis: FrontierAxis
    description: str
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    status: FrontierStatus = "open"
    evidence_refs: list[str] = Field(default_factory=list, alias="evidenceRefs")
    source: str = "runtime"


class WorkTreeResolutionPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    refine_pressure_threshold: float = Field(default=0.65, alias="refinePressureThreshold", ge=0.0, le=1.0)
    deliver_pressure_threshold: float = Field(default=0.25, alias="deliverPressureThreshold", ge=0.0, le=1.0)
    broad_node_detail_level: int = Field(default=1, alias="broadNodeDetailLevel", ge=0)
    max_inline_expected_evidence: int = Field(default=2, alias="maxInlineExpectedEvidence", ge=0)
    max_inline_text_chars: int = Field(default=480, alias="maxInlineTextChars", ge=1)
    max_inline_children: int = Field(default=0, alias="maxInlineChildren", ge=0)
    failure_retry_budget: int = Field(default=1, alias="failureRetryBudget", ge=0)
    plan_churn_refine_threshold: int = Field(default=2, alias="planChurnRefineThreshold", ge=0)


class DeliveryReadinessResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ready: bool
    blockers: list[str] = Field(default_factory=list)
    open_frontier_count: int = Field(default=0, alias="openFrontierCount")
    max_frontier_pressure: float = Field(default=0.0, alias="maxFrontierPressure")


class NodeResolutionAssessment(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    node_id: str = Field(alias="nodeId")
    recommended_action: ResolutionAction = Field(alias="recommendedAction")
    frontier_pressure: float = Field(alias="frontierPressure")
    saturation: float
    frontiers: list[FrontierItem] = Field(default_factory=list)
    delivery_readiness: DeliveryReadinessResult = Field(alias="deliveryReadiness")
    reasons: list[str] = Field(default_factory=list)


class ForkLaunchPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    max_forks: int = Field(default=3, alias="maxForks", ge=0)
    allow_recursive_fork: bool = Field(default=True, alias="allowRecursiveFork")
    reserve_parent_merge_slots: int = Field(default=0, alias="reserveParentMergeSlots", ge=0)
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


def build_long_run_core_frontiers(node_id: str | None = None) -> list[FrontierItem]:
    """Return the eight required ultra-long-task frontier seeds."""

    return [
        FrontierItem(
            id=frontier_id,
            nodeId=node_id,
            axis=axis,
            description=description,
            severity=severity,
            source="long-run-core-gap",
        )
        for frontier_id, axis, description, severity in LONG_RUN_CORE_GAP_FRONTIER_SPECS
    ]


def assess_node_resolution(
    work_tree: WorkTreeProtocol | Mapping[str, Any],
    node_id: str,
    *,
    graph_state: Mapping[str, Any] | None = None,
    policy: WorkTreeResolutionPolicy | Mapping[str, Any] | None = None,
) -> NodeResolutionAssessment:
    request_policy = WorkTreeResolutionPolicy.model_validate(policy or WorkTreeResolutionPolicy())
    protocol = WorkTreeProtocol.model_validate(work_tree)
    node_by_id = {node.id: node for node in protocol.nodes}
    node = node_by_id.get(node_id)
    if node is None:
        raise ValueError(f"Unknown work tree node: {node_id}")

    children = _direct_children(protocol, node)
    frontiers = _node_frontiers(
        protocol,
        node,
        children=children,
        graph_state=graph_state or {},
        policy=request_policy,
    )
    open_frontiers = _open_frontiers(frontiers)
    frontier_pressure = max((item.severity for item in open_frontiers), default=0.0)
    delivery_readiness = compute_delivery_readiness(
        protocol,
        node_id=node_id,
        graph_state={"frontierItems": [item.model_dump(by_alias=True, mode="json") for item in frontiers]},
        policy=request_policy,
    )
    reasons = _resolution_reasons(
        node,
        children=children,
        open_frontiers=open_frontiers,
        delivery_readiness=delivery_readiness,
        policy=request_policy,
    )
    return NodeResolutionAssessment(
        nodeId=node.id,
        recommendedAction=_recommended_resolution_action(
            node,
            children=children,
            open_frontiers=open_frontiers,
            delivery_readiness=delivery_readiness,
            frontier_pressure=frontier_pressure,
            policy=request_policy,
        ),
        frontierPressure=frontier_pressure,
        saturation=_node_saturation(frontier_pressure),
        frontiers=frontiers,
        deliveryReadiness=delivery_readiness,
        reasons=reasons,
    )


def compute_delivery_readiness(
    work_tree: WorkTreeProtocol | Mapping[str, Any],
    *,
    node_id: str | None = None,
    graph_state: Mapping[str, Any] | None = None,
    policy: WorkTreeResolutionPolicy | Mapping[str, Any] | None = None,
) -> DeliveryReadinessResult:
    request_policy = WorkTreeResolutionPolicy.model_validate(policy or WorkTreeResolutionPolicy())
    protocol = WorkTreeProtocol.model_validate(work_tree)
    target_node_id = node_id or protocol.root_node_id
    node_by_id = {node.id: node for node in protocol.nodes}
    node = node_by_id.get(target_node_id or "")
    if node is None:
        raise ValueError(f"Unknown delivery target work tree node: {target_node_id}")

    children = _direct_children(protocol, node)
    frontiers = _node_frontiers(
        protocol,
        node,
        children=children,
        graph_state=graph_state or {},
        policy=request_policy,
        include_derived=False,
    )
    open_frontiers = [
        item for item in _open_frontiers(frontiers) if item.severity > request_policy.deliver_pressure_threshold
    ]
    blockers: list[str] = []
    if open_frontiers:
        blockers.append("open-frontier-pressure")
    if any(child.status not in TERMINAL_WORK_TREE_NODE_STATUSES for child in children):
        blockers.append("unresolved-children")
    if node.status not in {"completed", "summarizing"} and protocol.status not in {"verified", "awaiting-approval", "completed"}:
        blockers.append("target-not-summarized")
    if _expected_evidence_missing(node):
        blockers.append("missing-target-evidence")
    return DeliveryReadinessResult(
        ready=not blockers,
        blockers=list(dict.fromkeys(blockers)),
        openFrontierCount=len(open_frontiers),
        maxFrontierPressure=max((item.severity for item in open_frontiers), default=0.0),
    )


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
    recursive_fork_blocked = not request.policy.allow_recursive_fork and parent.id != request.work_tree.root_node_id
    available_fork_slots = 0 if recursive_fork_blocked else _available_fork_slots(request.policy, active_fork_count)

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
    available_slots = _available_fork_slots(policy_model, effective_active_count)
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


def _available_fork_slots(policy: ForkLaunchPolicy, active_fork_count: int) -> int:
    return max(policy.max_forks - active_fork_count - policy.reserve_parent_merge_slots, 0)


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


def _node_frontiers(
    work_tree: WorkTreeProtocol,
    node: WorkTreeNode,
    *,
    children: Sequence[WorkTreeNode],
    graph_state: Mapping[str, Any],
    policy: WorkTreeResolutionPolicy,
    include_derived: bool = True,
) -> list[FrontierItem]:
    explicit = _frontiers_from_graph_state(graph_state, node_id=node.id)
    if not include_derived:
        return explicit

    derived: list[FrontierItem] = []
    if node.detail_level <= policy.broad_node_detail_level and _is_broad_node(node, children=children, policy=policy):
        derived.append(
            FrontierItem(
                id=f"{node.id}:broad-scope",
                nodeId=node.id,
                axis="deliverable",
                description="Node is a broad frame; keep it flexible but resolve it through smaller frontiers before delivery.",
                severity=0.72,
            )
        )
    unresolved_children = [child for child in children if child.status not in TERMINAL_WORK_TREE_NODE_STATUSES]
    if unresolved_children:
        derived.append(
            FrontierItem(
                id=f"{node.id}:unresolved-children",
                nodeId=node.id,
                axis="dependency",
                description="Child nodes are still unresolved; parent delivery should wait for merge or further refinement.",
                severity=min(0.95, 0.45 + 0.08 * len(unresolved_children)),
            )
        )
    failed_children = [child for child in children if child.status == "failed" and not child.failure_summary]
    if failed_children:
        derived.append(
            FrontierItem(
                id=f"{node.id}:failed-child-without-summary",
                nodeId=node.id,
                axis="failure",
                description="A failed child lacks failureSummary, so the parent cannot learn from the failed attempt.",
                severity=0.85,
            )
        )
    if _expected_evidence_missing(node):
        derived.append(
            FrontierItem(
                id=f"{node.id}:missing-evidence",
                nodeId=node.id,
                axis="verification",
                description="Expected evidence is declared but no produced evidence refs are attached.",
                severity=0.7,
            )
        )
    plan_churn = _plan_churn_count(graph_state, node.id)
    if plan_churn > policy.plan_churn_refine_threshold:
        derived.append(
            FrontierItem(
                id=f"{node.id}:plan-churn",
                nodeId=node.id,
                axis="plan-churn",
                description="Plan changed repeatedly; increase local resolution before more execution.",
                severity=min(1.0, 0.45 + 0.15 * plan_churn),
            )
        )
    failed_attempts = _failure_attempt_count(graph_state, node.id)
    if failed_attempts > policy.failure_retry_budget:
        derived.append(
            FrontierItem(
                id=f"{node.id}:failure-budget",
                nodeId=node.id,
                axis="failure",
                description="Failure budget exceeded at this resolution; split smaller or change approach.",
                severity=min(1.0, 0.55 + 0.15 * failed_attempts),
            )
        )
    if work_tree.root_node_id == node.id and _candidate_delivery_present(graph_state) and children and unresolved_children:
        derived.append(
            FrontierItem(
                id=f"{node.id}:premature-candidate-delivery",
                nodeId=node.id,
                axis="verification",
                description="A candidate delivery exists while child work is still open; record it as summary only.",
                severity=0.9,
            )
        )
    return [*explicit, *derived]


def _frontiers_from_graph_state(graph_state: Mapping[str, Any], *, node_id: str) -> list[FrontierItem]:
    result: list[FrontierItem] = []
    for raw_item in graph_state.get("frontierItems") or []:
        item = FrontierItem.model_validate(raw_item)
        if item.node_id not in {None, node_id}:
            continue
        result.append(item)
    return result


def _open_frontiers(frontiers: Sequence[FrontierItem]) -> list[FrontierItem]:
    return [item for item in frontiers if item.status == "open"]


def _is_broad_node(
    node: WorkTreeNode,
    *,
    children: Sequence[WorkTreeNode],
    policy: WorkTreeResolutionPolicy,
) -> bool:
    return (
        len(node.expected_evidence) > policy.max_inline_expected_evidence
        or len(node.node_text) > policy.max_inline_text_chars
        or len(children) > policy.max_inline_children
    )


def _expected_evidence_missing(node: WorkTreeNode) -> bool:
    return bool(node.expected_evidence) and not node.produced_evidence_refs and node.status not in {
        "failed",
        "skipped",
    }


def _plan_churn_count(graph_state: Mapping[str, Any], node_id: str) -> int:
    raw = graph_state.get("planChurn")
    if isinstance(raw, Mapping):
        return int(raw.get(node_id) or 0)
    return int(graph_state.get("planChurnCount") or 0)


def _failure_attempt_count(graph_state: Mapping[str, Any], node_id: str) -> int:
    raw = graph_state.get("failureAttempts")
    if isinstance(raw, Mapping):
        return int(raw.get(node_id) or 0)
    return int(graph_state.get("failureAttemptCount") or 0)


def _candidate_delivery_present(graph_state: Mapping[str, Any]) -> bool:
    return bool(
        graph_state.get("candidateDelivery")
        or graph_state.get("candidateDeliveryText")
        or graph_state.get("deliveryCandidate")
    )


def _recommended_resolution_action(
    node: WorkTreeNode,
    *,
    children: Sequence[WorkTreeNode],
    open_frontiers: Sequence[FrontierItem],
    delivery_readiness: DeliveryReadinessResult,
    frontier_pressure: float,
    policy: WorkTreeResolutionPolicy,
) -> ResolutionAction:
    if node.status == "blocked":
        return "block"
    if any(item.axis in {"failure", "plan-churn", "deliverable", "risk", "cost", "conflict"} for item in open_frontiers) and (
        frontier_pressure >= policy.refine_pressure_threshold
    ):
        return "refine"
    if any(child.status not in TERMINAL_WORK_TREE_NODE_STATUSES for child in children):
        return "merge"
    if any(item.axis in {"unknown", "verification", "reliability", "durability", "transaction", "evaluation", "observability"} for item in open_frontiers):
        return "work"
    if delivery_readiness.ready:
        return "deliver"
    if frontier_pressure >= policy.refine_pressure_threshold:
        return "refine"
    return "work"


def _resolution_reasons(
    node: WorkTreeNode,
    *,
    children: Sequence[WorkTreeNode],
    open_frontiers: Sequence[FrontierItem],
    delivery_readiness: DeliveryReadinessResult,
    policy: WorkTreeResolutionPolicy,
) -> list[str]:
    reasons: list[str] = []
    if node.status == "blocked":
        reasons.append("node-blocked")
    if any(item.severity >= policy.refine_pressure_threshold for item in open_frontiers):
        reasons.append("frontier-pressure-above-refine-threshold")
    if any(child.status not in TERMINAL_WORK_TREE_NODE_STATUSES for child in children):
        reasons.append("unresolved-children")
    if not delivery_readiness.ready:
        reasons.extend(f"delivery-blocked:{blocker}" for blocker in delivery_readiness.blockers)
    if not reasons:
        reasons.append("frontier-pressure-low")
    return list(dict.fromkeys(reasons))


def _node_saturation(frontier_pressure: float) -> float:
    return round(max(0.0, min(1.0, 1.0 - frontier_pressure)), 4)
