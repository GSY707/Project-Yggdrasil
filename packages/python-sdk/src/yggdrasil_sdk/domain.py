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


class SpaceMountRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    host_space_id: str = Field(alias="hostSpaceId")
    mounted_space_id: str = Field(alias="mountedSpaceId")
    mount_mode: Literal["readonly", "copy-on-write", "bidirectional"] = Field(alias="mountMode")
    status: Literal["active", "disabled", "detached"]
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class PermissionTupleRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    subject: str
    relation: str
    resource: str
    condition: dict[str, Any] | None = None
    effect: Literal["allow", "deny"]
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
    window_index: int = Field(default=1, alias="windowIndex")
    source_work_tree_node_id: str | None = Field(default=None, alias="sourceWorkTreeNodeId")
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
    source_type: Literal["external", "memory", "human", "inference", "system", "assistant-memory-tag"] = Field(alias="sourceType")
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
    reverse_trace_mode: bool = Field(default=False, alias="reverseTraceMode")
    work_tree_node_id: str | None = Field(default=None, alias="workTreeNodeId")
    window_index: int | None = Field(default=None, alias="windowIndex")
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
    app_id: str = Field(alias="appId")
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    title: str
    goal: str
    status: Literal[
        "draft",
        "queued",
        "running",
        "paused",
        "resume-blocked",
        "restart-requested",
        "restarting",
        "cancelling",
        "awaiting-approval",
        "completed",
        "failed",
        "cancelled",
    ]
    current_focus: str | None = Field(default=None, alias="currentFocus")
    current_objective: str | None = Field(default=None, alias="currentObjective")
    resume_message: str | None = Field(default=None, alias="resumeMessage")
    restart_message: str | None = Field(default=None, alias="restartMessage")
    owner_profile_id: str = Field(alias="ownerProfileId")
    execution_root_node_id: str | None = Field(default=None, alias="executionRootNodeId")
    active_snapshot_id: str | None = Field(default=None, alias="activeSnapshotId")
    active_resume_attempt_id: str | None = Field(default=None, alias="activeResumeAttemptId")
    resume_blocked_reason: str | None = Field(default=None, alias="resumeBlockedReason")
    pending_control_intent: str | None = Field(default=None, alias="pendingControlIntent")
    window_index: int = Field(default=1, alias="windowIndex")
    restart_count: int = Field(default=0, alias="restartCount")
    cumulative_window_span_tokens: int = Field(default=0, alias="cumulativeWindowSpanTokens")
    carry_forward_loss_count: int = Field(default=0, alias="carryForwardLossCount")
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
    app_id: str = Field(alias="appId")
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
    window_index: int = Field(default=1, alias="windowIndex")
    restart_count: int = Field(default=0, alias="restartCount")
    cumulative_window_span_tokens: int = Field(default=0, alias="cumulativeWindowSpanTokens")
    input_tokens_used: int = Field(alias="inputTokensUsed")
    output_tokens_used: int = Field(alias="outputTokensUsed")
    cost_used: float = Field(alias="costUsed")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")


class TaskResumeAttemptRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    snapshot_id: str = Field(alias="snapshotId")
    requested_by: dict[str, Any] = Field(default_factory=dict, alias="requestedBy")
    status: Literal["queued", "leased", "restoring", "running", "blocked", "cancelled", "completed"]
    lease_owner: str | None = Field(default=None, alias="leaseOwner")
    lease_until: datetime | None = Field(default=None, alias="leaseUntil")
    blocker_code: str | None = Field(default=None, alias="blockerCode")
    blocker_message: str | None = Field(default=None, alias="blockerMessage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class RuntimeWorkItemRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    queue: str
    task_id: str | None = Field(default=None, alias="taskId")
    activity: str
    intent: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: Literal["queued", "leased", "completed", "failed", "cancelled", "reclaimable"]
    lease_owner: str | None = Field(default=None, alias="leaseOwner")
    lease_until: datetime | None = Field(default=None, alias="leaseUntil")
    attempt: int = 1
    last_error: str | None = Field(default=None, alias="lastError")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")


class TaskBranchRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    parent_task_id: str = Field(alias="parentTaskId")
    child_task_id: str = Field(alias="childTaskId")
    source_snapshot_id: str = Field(alias="sourceSnapshotId")
    source_snapshot_checksum: str = Field(alias="sourceSnapshotChecksum")
    label: str | None = None
    created_by_user_id: str = Field(alias="createdByUserId")
    created_at: datetime = Field(alias="createdAt")


class ModelInvocationRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    app_id: str = Field(alias="appId")
    project_id: str = Field(alias="projectId")
    task_id: str | None = Field(default=None, alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    route_decision_id: str | None = Field(default=None, alias="routeDecisionId")
    requested_model: str = Field(alias="requestedModel")
    requested_provider: str | None = Field(default=None, alias="requestedProvider")
    resolved_model: str = Field(alias="resolvedModel")
    resolved_provider: str | None = Field(default=None, alias="resolvedProvider")
    invocation_kind: Literal["chat-completion"] = Field(alias="invocationKind")
    status: Literal["queued", "running", "completed", "failed", "fallback"]
    trace_id: str | None = Field(default=None, alias="traceId")
    prompt_compile_artifact_id: str | None = Field(default=None, alias="promptCompileArtifactId")
    request_ref: ExternalRef | None = Field(default=None, alias="requestRef")
    response_ref: ExternalRef | None = Field(default=None, alias="responseRef")
    output_labels: list[str] = Field(default_factory=list, alias="outputLabels")
    assistant_text_summary: str | None = Field(default=None, alias="assistantTextSummary")
    input_tokens_used: int = Field(alias="inputTokensUsed")
    output_tokens_used: int = Field(alias="outputTokensUsed")
    cost_used: float = Field(alias="costUsed")
    latency_ms: float | None = Field(default=None, alias="latencyMs")
    error_summary: str | None = Field(default=None, alias="errorSummary")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    created_at: datetime = Field(alias="createdAt")


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


class MailboxMessageRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    task_id: str = Field(alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    sender: ActorRef
    message_kind: str = Field(alias="messageKind")
    subject: str
    body: str
    work_tree_node_id: str | None = Field(default=None, alias="workTreeNodeId")
    wake_on_message: bool = Field(default=True, alias="wakeOnMessage")
    status: Literal["pending", "delivered", "acknowledged"]
    payload_ref: ExternalRef | None = Field(default=None, alias="payloadRef")
    created_at: datetime = Field(alias="createdAt")
    delivered_at: datetime | None = Field(default=None, alias="deliveredAt")
    acknowledged_at: datetime | None = Field(default=None, alias="acknowledgedAt")


class SideChannelEventRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    task_id: str = Field(alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    source: ActorRef
    event_kind: str = Field(alias="eventKind")
    level: Literal["info", "warning", "error"]
    summary: str
    work_tree_node_id: str | None = Field(default=None, alias="workTreeNodeId")
    payload_ref: ExternalRef | None = Field(default=None, alias="payloadRef")
    created_at: datetime = Field(alias="createdAt")


class EvaluationSuiteRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    domain: Literal["trpg", "coding", "writing", "research", "generic"]
    metric_refs: list[str] = Field(default_factory=list, alias="metricRefs")
    created_at: datetime = Field(alias="createdAt")


class EvaluationRunRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    suite_id: str = Field(alias="suiteId")
    project_id: str = Field(alias="projectId")
    subject_kind: Literal["module", "model", "retrieval-policy", "workflow"] = Field(alias="subjectKind")
    subject_ref: str = Field(alias="subjectRef")
    status: Literal["queued", "running", "completed", "failed"]
    metrics_ref: ExternalRef | None = Field(default=None, alias="metricsRef")
    started_at: datetime | None = Field(default=None, alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    created_at: datetime = Field(alias="createdAt")


class AssetRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    space_id: str = Field(alias="spaceId")
    branch_id: str = Field(alias="branchId")
    owner_node_id: str | None = Field(default=None, alias="ownerNodeId")
    media_type: str = Field(alias="mediaType")
    role: Literal["original", "derived", "preview", "thumbnail", "transcript"]
    storage_key: str = Field(alias="storageKey")
    checksum: str
    source_ref: ExternalRef | None = Field(default=None, alias="sourceRef")
    related_work_tree_node_ids: list[str] = Field(default_factory=list, alias="relatedWorkTreeNodeIds")
    duration_ms: int | None = Field(default=None, alias="durationMs")
    width: int | None = Field(default=None, alias="width")
    height: int | None = Field(default=None, alias="height")
    created_at: datetime = Field(alias="createdAt")
    created_by: ActorRef = Field(alias="createdBy")


class AssetSegmentRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    asset_id: str = Field(alias="assetId")
    ordinal: int
    start_offset: int = Field(alias="startOffset")
    end_offset: int = Field(alias="endOffset")
    text_excerpt: str | None = Field(default=None, alias="textExcerpt")
    summary: str | None = None
    embedding_id: str | None = Field(default=None, alias="embeddingId")
    created_at: datetime = Field(alias="createdAt")


class AssetEmbeddingRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    owner_kind: Literal["asset", "asset-segment", "node"] = Field(alias="ownerKind")
    owner_id: str = Field(alias="ownerId")
    model: str
    dimension: int
    vector_ref: ExternalRef = Field(alias="vectorRef")
    created_at: datetime = Field(alias="createdAt")


class DatasetVersionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    dataset_name: str = Field(alias="datasetName")
    version: str
    source_filter: dict[str, Any] = Field(default_factory=dict, alias="sourceFilter")
    storage_key: str = Field(alias="storageKey")
    row_count: int = Field(alias="rowCount")
    created_at: datetime = Field(alias="createdAt")


class ModelArtifactRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    base_model: str = Field(alias="baseModel")
    tuning_method: Literal["sft", "dpo", "distillation", "adapter"] = Field(alias="tuningMethod")
    dataset_version_id: str = Field(alias="datasetVersionId")
    metrics_ref: ExternalRef | None = Field(default=None, alias="metricsRef")
    storage_key: str = Field(alias="storageKey")
    status: Literal["staged", "validated", "promoted", "retired"]
    created_at: datetime = Field(alias="createdAt")


class PromptProfileVersionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    prompt_profile_id: str = Field(alias="promptProfileId")
    name: str
    version: str
    run_scope: str = Field(alias="runScope")
    body: dict[str, Any]
    content_hash: str = Field(alias="contentHash")
    created_at: datetime = Field(alias="createdAt")


class SeedTemplateVersionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    seed_template_id: str = Field(alias="seedTemplateId")
    name: str
    version: str
    domain: str
    scenario: str
    body: dict[str, Any]
    content_hash: str = Field(alias="contentHash")
    created_at: datetime = Field(alias="createdAt")


class PromptCompileArtifactRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    app_id: str = Field(alias="appId")
    project_id: str = Field(alias="projectId")
    task_id: str | None = Field(default=None, alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    model_invocation_id: str | None = Field(default=None, alias="modelInvocationId")
    prompt_profile_version_id: str = Field(alias="promptProfileVersionId")
    seed_template_version_id: str | None = Field(default=None, alias="seedTemplateVersionId")
    run_type: str = Field(alias="runType")
    task_type: str = Field(alias="taskType")
    scenario: str | None = None
    registered_tools: list[dict[str, Any]] = Field(default_factory=list, alias="registeredTools")
    boot_sections: dict[str, str] = Field(default_factory=dict, alias="bootSections")
    system_sections: dict[str, str] = Field(default_factory=dict, alias="systemSections")
    user_sections: dict[str, str] = Field(default_factory=dict, alias="userSections")
    work_tree_snapshot: dict[str, Any] | None = Field(default=None, alias="workTreeSnapshot")
    takeover_protocol_snapshot: dict[str, Any] | None = Field(default=None, alias="takeoverProtocolSnapshot")
    compiled_messages_ref: ExternalRef = Field(alias="compiledMessagesRef")
    content_hash: str = Field(alias="contentHash")
    created_at: datetime = Field(alias="createdAt")
