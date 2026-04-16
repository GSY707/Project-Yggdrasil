from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .contracts import ActorRef, BudgetState, EntityRef, ExternalRef


class ProjectRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    display_name: str = Field(alias="displayName")
    status: Literal["active", "archived", "deleted"]
    export_policy: Literal["project-package-only"] = Field(alias="exportPolicy")
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class SpaceRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_type: Literal["default", "personal", "shared", "system"] = Field(alias="spaceType")
    status: Literal["active", "archived", "deleted"]
    owner_subject: str | None = Field(default=None, alias="ownerSubject")
    created_at: datetime = Field(alias="createdAt")


class MemoryBranchRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    name: str
    base_branch_id: str | None = Field(default=None, alias="baseBranchId")
    head_ref: str | None = Field(default=None, alias="headRef")
    status: Literal["active", "frozen", "merged", "deleted"]
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class NodeRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    parent_id: str | None = Field(default=None, alias="parentId")
    root_branch: Literal["identity", "context", "execution", "none"] = Field(alias="rootBranch")
    node_type: Literal["root", "identity", "context", "task", "summary", "detail", "temporary", "system", "reference"] = Field(alias="nodeType")
    status: Literal["active", "temporary", "merged", "archived", "deleted"]
    title: str
    content: str
    detail_level: int = Field(alias="detailLevel")
    importance: float
    stability: float
    forget_rate: float = Field(alias="forgetRate")
    feedforward_score: float = Field(alias="feedforwardScore")
    access_score: float = Field(alias="accessScore")
    activity_k: float = Field(alias="activityK")
    float_score: float = Field(alias="floatScore")
    latest_version_id: str = Field(alias="latestVersionId")
    merged_into_node_id: str | None = Field(default=None, alias="mergedIntoNodeId")
    children_count: int = Field(alias="childrenCount")
    edge_count: int = Field(alias="edgeCount")
    tree_path: str | None = Field(default=None, alias="treePath")
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")
    updated_at: datetime = Field(alias="updatedAt")
    updated_by: ActorRef = Field(alias="updatedBy")


class EdgeRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    from_node_id: str = Field(alias="fromNodeId")
    to_node_id: str = Field(alias="toNodeId")
    relation_type: str = Field(alias="relationType")
    weight: float
    reason: str
    evidence_annotation_ids: list[str] = Field(default_factory=list, alias="evidenceAnnotationIds")
    status: Literal["active", "deprecated", "deleted"]
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")
    updated_at: datetime = Field(alias="updatedAt")
    updated_by: ActorRef = Field(alias="updatedBy")


class NodeVersionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    node_id: str = Field(alias="nodeId")
    version_no: int = Field(alias="versionNo")
    title_snapshot: str = Field(alias="titleSnapshot")
    content_snapshot: str = Field(alias="contentSnapshot")
    parent_id_snapshot: str | None = Field(default=None, alias="parentIdSnapshot")
    score_snapshot: dict[str, float] = Field(alias="scoreSnapshot")
    change_reason: str = Field(alias="changeReason")
    derived_from_version_id: str | None = Field(default=None, alias="derivedFromVersionId")
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class SourceAnnotationRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    branch_id: str = Field(alias="branchId")
    owner_kind: Literal["node", "edge", "version", "task", "pr", "package"] = Field(alias="ownerKind")
    owner_id: str = Field(alias="ownerId")
    source_type: Literal["external", "memory", "human", "inference", "system"] = Field(alias="sourceType")
    source_ref: ExternalRef | None = Field(default=None, alias="sourceRef")
    excerpt: str | None = None
    inference_summary: str | None = Field(default=None, alias="inferenceSummary")
    evidence_refs: list[EntityRef] = Field(default_factory=list, alias="evidenceRefs")
    confidence: float
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class ImportPolicy(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    segment_target_chars: int = Field(default=320, alias="segmentTargetChars")
    allow_discard_low_value: bool = Field(default=False, alias="allowDiscardLowValue")
    preferred_builder_model: str | None = Field(default=None, alias="preferredBuilderModel")
    tree_preference_prompt: str | None = Field(default=None, alias="treePreferencePrompt")
    link_strategy: list[Literal["vector", "ppr", "keyword", "hybrid"]] = Field(
        default_factory=lambda: ["keyword"],
        alias="linkStrategy",
    )
    merge_policy: Literal["conservative", "balanced", "aggressive"] = Field(
        default="balanced",
        alias="mergePolicy",
    )


class RetrievalRequestRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    query_text: str | None = Field(default=None, alias="queryText")
    seed_node_refs: list[EntityRef] = Field(default_factory=list, alias="seedNodeRefs")
    traversal_start: Literal["roots", "seeds", "mixed"] = Field(default="mixed", alias="traversalStart")
    expansion_mode: Literal["parallel", "serial"] = Field(default="parallel", alias="expansionMode")
    read_depth: int = Field(default=2, alias="readDepth")
    lateral_hops: int = Field(default=1, alias="lateralHops")
    max_related_nodes: int = Field(default=4, alias="maxRelatedNodes")
    max_leaf_nodes: int = Field(default=6, alias="maxLeafNodes")
    precision_mode: Literal["coarse", "balanced", "fine"] = Field(default="balanced", alias="precisionMode")
    include_natural_language_summary: bool = Field(default=True, alias="includeNaturalLanguageSummary")
    include_child_names: bool = Field(default=True, alias="includeChildNames")
    include_related_names: bool = Field(default=True, alias="includeRelatedNames")
    token_budget: int | None = Field(default=None, alias="tokenBudget")
    created_at: datetime = Field(alias="createdAt")


class RetrievalBundle(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    request_id: str = Field(alias="requestId")
    matched_node_refs: list[EntityRef] = Field(default_factory=list, alias="matchedNodeRefs")
    node_payloads: list[dict[str, Any]] = Field(default_factory=list, alias="nodePayloads")
    child_name_map: dict[str, list[str]] = Field(default_factory=dict, alias="childNameMap")
    related_name_map: dict[str, list[str]] = Field(default_factory=dict, alias="relatedNameMap")
    source_annotation_refs: list[str] = Field(default_factory=list, alias="sourceAnnotationRefs")
    natural_language_summary: str | None = Field(default=None, alias="naturalLanguageSummary")
    truncated: bool = False
    generated_at: datetime = Field(alias="generatedAt")


class ImportJobRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    branch_id: str = Field(alias="branchId")
    source_kind: Literal["file", "stream", "package", "clipboard"] = Field(alias="sourceKind")
    status: Literal["accepted", "preprocessing", "pre-reading", "planning", "materializing", "completed", "failed", "cancelled"]
    import_policy: ImportPolicy = Field(alias="importPolicy")
    requested_by: ActorRef = Field(alias="requestedBy")
    token_budget: int | None = Field(default=None, alias="tokenBudget")
    cost_budget: float | None = Field(default=None, alias="costBudget")
    failure_reason: str | None = Field(default=None, alias="failureReason")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    created_at: datetime = Field(alias="createdAt")


class ImportFragmentRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    import_job_id: str = Field(alias="importJobId")
    ordinal: int
    raw_ref: ExternalRef = Field(alias="rawRef")
    normalized_text: str = Field(alias="normalizedText")
    approx_tokens: int = Field(alias="approxTokens")
    related_hints: list[str] = Field(default_factory=list, alias="relatedHints")
    created_at: datetime = Field(alias="createdAt")


class TreePlanRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    import_job_id: str = Field(alias="importJobId")
    status: Literal["proposed", "accepted", "materialized", "rejected", "superseded"]
    candidate_node_payloads: list[dict[str, Any]] = Field(default_factory=list, alias="candidateNodePayloads")
    candidate_edge_payloads: list[dict[str, Any]] = Field(default_factory=list, alias="candidateEdgePayloads")
    candidate_source_annotations: list[dict[str, Any]] = Field(default_factory=list, alias="candidateSourceAnnotations")
    discarded_fragment_refs: list[str] = Field(default_factory=list, alias="discardedFragmentRefs")
    rationale: str
    proposed_by: ActorRef = Field(alias="proposedBy")
    created_at: datetime = Field(alias="createdAt")


class TaskRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    title: str
    goal: str
    status: Literal["draft", "queued", "running", "pause-requested", "paused", "restart-requested", "restarting", "completed", "failed", "cancelled"]
    current_focus: str | None = Field(default=None, alias="currentFocus")
    current_objective: str | None = Field(default=None, alias="currentObjective")
    resume_message: str | None = Field(default=None, alias="resumeMessage")
    restart_message: str | None = Field(default=None, alias="restartMessage")
    owner_profile_id: str = Field(alias="ownerProfileId")
    execution_root_node_id: str | None = Field(default=None, alias="executionRootNodeId")
    active_snapshot_id: str | None = Field(default=None, alias="activeSnapshotId")
    budget: BudgetState
    pause_requested: bool = Field(alias="pauseRequested")
    last_safe_stop_at: datetime | None = Field(default=None, alias="lastSafeStopAt")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class AgentRunRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    project_id: str = Field(alias="projectId")
    branch_id: str = Field(alias="branchId")
    parent_run_id: str | None = Field(default=None, alias="parentRunId")
    run_type: Literal["main", "subagent", "maintenance", "evaluation"] = Field(alias="runType")
    selected_model: str = Field(alias="selectedModel")
    selected_provider: str | None = Field(default=None, alias="selectedProvider")
    route_decision_id: str | None = Field(default=None, alias="routeDecisionId")
    status: Literal["initializing", "mounting", "running", "waiting-tool", "draining", "pausing", "paused", "completed", "failed", "aborted"]
    next_objective: str | None = Field(default=None, alias="nextObjective")
    input_tokens_used: int = Field(alias="inputTokensUsed")
    output_tokens_used: int = Field(alias="outputTokensUsed")
    cost_used: float = Field(alias="costUsed")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")


class OutboxRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str | None = Field(default=None, alias="projectId")
    aggregate_type: str = Field(alias="aggregateType")
    aggregate_id: str = Field(alias="aggregateId")
    event_type: str = Field(alias="eventType")
    event_version: int = Field(alias="eventVersion")
    payload_ref: ExternalRef = Field(alias="payloadRef")
    publish_status: Literal["pending", "publishing", "published", "dead-letter"] = Field(alias="publishStatus")
    attempts: int
    available_at: datetime = Field(alias="availableAt")
    published_at: datetime | None = Field(default=None, alias="publishedAt")
    last_error: str | None = Field(default=None, alias="lastError")
    created_at: datetime = Field(alias="createdAt")