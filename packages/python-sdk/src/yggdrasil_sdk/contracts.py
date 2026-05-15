from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExternalRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["url", "file", "object-storage", "package-entry", "citation"]
    locator: str
    checksum: str | None = None


class ActorRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: Literal["user", "agent", "module", "system"]
    id: str


class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str
    id: str


class BudgetState(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    token_budget_total: int | None = Field(default=None, alias="tokenBudgetTotal")
    token_budget_used: int = Field(default=0, alias="tokenBudgetUsed")
    cost_budget_total: float | None = Field(default=None, alias="costBudgetTotal")
    cost_budget_used: float = Field(default=0.0, alias="costBudgetUsed")
    self_think_token_limit: int | None = Field(default=None, alias="selfThinkTokenLimit")
    child_budget_mode: Literal["inherit", "fixed", "capped"] = Field(
        default="inherit",
        alias="childBudgetMode",
    )
    max_sub_agents: int | None = Field(default=None, alias="maxSubAgents")


class ToolDescriptor(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    module_id: str = Field(alias="moduleId")
    version: str
    display_name: str = Field(alias="displayName")
    description: str | None = None
    schema_ref: str = Field(alias="schemaRef")
    execution_mode: Literal["sync", "async", "stream"] = Field(alias="executionMode")
    timeout_ms: int = Field(default=5000, alias="timeoutMs")
    idempotent: bool = True
    permission_required: list[str] = Field(default_factory=list, alias="permissionRequired")
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    implementation_ref: str | None = Field(default=None, alias="implementationRef")


class ModuleManifestSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    module_id: str = Field(alias="moduleId")
    display_name: str = Field(alias="displayName")
    version: str
    runtime_mode: str = Field(alias="runtimeMode")
    manifest_path: str = Field(alias="manifestPath")
    category: str | None = None
    owner: str | None = None
    description: str | None = None
    entry_point: str | None = Field(default=None, alias="entryPoint")
    protocol: str | None = None
    kernel_compatibility: str | None = Field(default=None, alias="kernelCompatibility")
    hooks: list[str] = Field(default_factory=list)
    publishes: list[str] = Field(default_factory=list)
    subscribes: list[str] = Field(default_factory=list)
    requested_permissions: list[str] = Field(default_factory=list, alias="requestedPermissions")


class ModuleInstallRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    module_id: str = Field(alias="moduleId")
    module_version: str = Field(alias="moduleVersion")
    desired_state: Literal["enabled", "disabled"] = Field(alias="desiredState")
    lifecycle_state: str = Field(alias="lifecycleState")
    runtime_mode: str = Field(alias="runtimeMode")
    manifest_ref: ExternalRef = Field(alias="manifestRef")
    config_binding_id: str | None = Field(default=None, alias="configBindingId")
    installed_at: datetime | None = Field(default=None, alias="installedAt")
    enabled_at: datetime | None = Field(default=None, alias="enabledAt")
    disabled_at: datetime | None = Field(default=None, alias="disabledAt")
    last_error: str | None = Field(default=None, alias="lastError")


class ModuleConfigBinding(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    module_install_id: str = Field(alias="moduleInstallId")
    config_schema_version: str = Field(alias="configSchemaVersion")
    effective_config_ref: ExternalRef = Field(alias="effectiveConfigRef")
    source_mode: Literal["database-primary-file-overlay"] = Field(alias="sourceMode")
    updated_at: datetime = Field(alias="updatedAt")
    updated_by: ActorRef = Field(alias="updatedBy")


class HookContributionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    module_install_id: str = Field(alias="moduleInstallId")
    hook_name: str = Field(alias="hookName")
    implementation_ref: str = Field(alias="implementationRef")
    execution_order: int = Field(alias="executionOrder")
    timeout_ms: int = Field(alias="timeoutMs")
    side_effects: Literal["none", "read-only", "controlled-write"] = Field(alias="sideEffects")
    enabled: bool
    created_at: datetime = Field(alias="createdAt")


class EventSubscriptionRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    module_install_id: str = Field(alias="moduleInstallId")
    event_type: str = Field(alias="eventType")
    consumer_group: str = Field(alias="consumerGroup")
    delivery_mode: Literal["at-least-once"] = Field(alias="deliveryMode")
    status: Literal["active", "paused", "error"]
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class HealthReport(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str
    module_install_id: str = Field(alias="moduleInstallId")
    status: Literal["healthy", "degraded", "unhealthy", "quarantined"]
    summary: str
    details_ref: ExternalRef | None = Field(default=None, alias="detailsRef")
    observed_at: datetime = Field(alias="observedAt")


class EventEnvelope(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    specversion: str = "1.0"
    event_type: str = Field(alias="eventType")
    event_version: int = Field(default=1, alias="eventVersion")
    event_id: str = Field(alias="eventId")
    occurred_at: datetime = Field(alias="occurredAt")
    source: str
    actor: ActorRef | None = None
    project_id: str = Field(alias="projectId")
    space_id: str | None = Field(default=None, alias="spaceId")
    branch_id: str | None = Field(default=None, alias="branchId")
    task_id: str | None = Field(default=None, alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    correlation_id: str = Field(alias="correlationId")
    causation_id: str | None = Field(default=None, alias="causationId")
    schema_ref: str = Field(alias="schemaRef")
    payload: dict[str, Any]


class ModuleEventEmission(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    aggregate_type: str = Field(alias="aggregateType")
    aggregate_id: str = Field(alias="aggregateId")
    event_type: str = Field(alias="eventType")
    payload: dict[str, Any]
    event_version: int = Field(default=1, alias="eventVersion")
    source: str | None = None
    project_id: str | None = Field(default=None, alias="projectId")
    space_id: str | None = Field(default=None, alias="spaceId")
    branch_id: str | None = Field(default=None, alias="branchId")
    task_id: str | None = Field(default=None, alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    correlation_id: str | None = Field(default=None, alias="correlationId")
    causation_id: str | None = Field(default=None, alias="causationId")
    schema_ref: str | None = Field(default=None, alias="schemaRef")


class EventHandlingResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    status: Literal["handled", "ignored", "failed"]
    handled: bool = False
    summary: str | None = None
    emitted_events: list[ModuleEventEmission] = Field(default_factory=list, alias="emittedEvents")
    health_status: Literal["healthy", "degraded", "unhealthy", "quarantined"] | None = Field(
        default=None,
        alias="healthStatus",
    )


class RootMountPackage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    project_id: str = Field(alias="projectId")
    branch_id: str = Field(alias="branchId")
    system_intro: str = Field(alias="systemIntro")
    identity_refs: list[EntityRef] = Field(default_factory=list, alias="identityRefs")
    context_refs: list[EntityRef] = Field(default_factory=list, alias="contextRefs")
    execution_refs: list[EntityRef] = Field(default_factory=list, alias="executionRefs")
    root_summary: str = Field(alias="rootSummary")
    task_objective: str | None = Field(default=None, alias="taskObjective")
    resume_message: str | None = Field(default=None, alias="resumeMessage")
    budget_state: BudgetState = Field(alias="budgetState")
    active_capabilities: list[str] = Field(default_factory=list, alias="activeCapabilities")
    generated_at: datetime = Field(alias="generatedAt")


class TaskSnapshotSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    app_id: str = Field(alias="appId")
    task_id: str = Field(alias="taskId")
    agent_run_id: str = Field(alias="agentRunId")
    project_id: str = Field(alias="projectId")
    branch_id: str = Field(alias="branchId")
    snapshot_type: Literal["pause", "restart", "checkpoint"] = Field(alias="snapshotType")
    status: Literal["created", "flushed", "restorable", "consumed", "superseded"]
    resume_token: str = Field(alias="resumeToken")
    context_ref: ExternalRef = Field(alias="contextRef")
    root_mount_ref: ExternalRef = Field(alias="rootMountRef")
    pending_writes: list[EntityRef] = Field(default_factory=list, alias="pendingWrites")
    pending_actions: list[dict[str, Any]] = Field(default_factory=list, alias="pendingActions")
    resume_message: str | None = Field(default=None, alias="resumeMessage")
    safe_stop_reason: str = Field(alias="safeStopReason")
    created_at: datetime = Field(alias="createdAt")
    consumed_at: datetime | None = Field(default=None, alias="consumedAt")
    safe_to_pause: bool = Field(default=True, alias="safeToPause")
    blockers: list[str] = Field(default_factory=list)


class ContextPruningPlan(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str = Field(alias="taskId")
    source_run_id: str = Field(alias="sourceRunId")
    next_objective: str = Field(alias="nextObjective")
    protected_refs: list[EntityRef] = Field(default_factory=list, alias="protectedRefs")
    retained_refs: list[EntityRef] = Field(default_factory=list, alias="retainedRefs")
    compressed_refs: list[EntityRef] = Field(default_factory=list, alias="compressedRefs")
    dropped_refs: list[EntityRef] = Field(default_factory=list, alias="droppedRefs")
    rationale: str
    status: Literal["proposed", "executed", "verified", "failed"]
    created_by: ActorRef = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")


class TaskTakeoverAmbiguity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    prompt: str
    reason: str | None = None
    required: bool = True


class TaskTakeoverConstraint(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    category: Literal["objective", "scope", "budget", "runtime", "tooling", "delivery", "policy", "environment"]
    label: str
    value: str
    required: bool = True
    source: str | None = None


class TaskTakeoverPlanStep(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    title: str
    instructions: str
    phase: Literal["objective", "constraints", "plan", "execute", "verify", "deliver"]
    status: Literal["pending", "in-progress", "completed", "blocked", "skipped"] = "pending"
    expected_evidence: list[str] = Field(default_factory=list, alias="expectedEvidence")
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")


class WorkTreeNode(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    title: str
    phase: Literal["planning", "executing", "recovering", "restarting", "verification", "delivery"]
    status: Literal["pending", "in-progress", "completed", "blocked", "skipped"] = "pending"
    plan_step_ids: list[str] = Field(default_factory=list, alias="planStepIds")
    constraint_ids: list[str] = Field(default_factory=list, alias="constraintIds")
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")
    expected_evidence: list[str] = Field(default_factory=list, alias="expectedEvidence")
    recovery_anchor: str | None = Field(default=None, alias="recoveryAnchor")


class WorkTreeProtocol(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version: str = "0.1.0"
    root_objective: str = Field(alias="rootObjective")
    status: Literal["planned", "active", "paused", "verified", "completed"]
    current_node_id: str | None = Field(default=None, alias="currentNodeId")
    nodes: list[WorkTreeNode] = Field(default_factory=list)
    recovery_anchor: str | None = Field(default=None, alias="recoveryAnchor")
    entropy_budget_remaining: int = Field(default=0, alias="entropyBudgetRemaining")


class TaskTakeoverVerificationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    label: str
    status: Literal["passed", "warning", "failed", "not-run"]
    detail: str | None = None


class TaskTakeoverDeliverySection(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    section: Literal["result", "evidence", "pending", "incomplete"]
    content: str
    status: Literal["present", "missing", "not-applicable"] = "present"


class TaskTakeoverMetrics(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    plan_quality_score_0_100: float = Field(default=0.0, alias="planQualityScore0_100")
    rework_count: int = Field(default=0, alias="reworkCount")
    rework_rate: float = Field(default=0.0, alias="reworkRate")
    clarification_needed: bool = Field(default=False, alias="clarificationNeeded")
    delivery_completeness_score_0_100: float = Field(default=0.0, alias="deliveryCompletenessScore0_100")
    verification_pass_rate: float = Field(default=0.0, alias="verificationPassRate")


class TaskTakeoverProtocol(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    version: str = "0.1.0"
    task_id: str = Field(alias="taskId")
    task_type: str = Field(alias="taskType")
    run_type: str = Field(alias="runType")
    current_phase: Literal["objective", "constraints", "plan", "execute", "verify", "deliver"] = Field(alias="currentPhase")
    status: Literal["prepared", "executing", "verified", "completed", "needs-clarification"]
    objective: str
    objective_summary: str = Field(alias="objectiveSummary")
    ambiguities: list[TaskTakeoverAmbiguity] = Field(default_factory=list)
    constraints: list[TaskTakeoverConstraint] = Field(default_factory=list)
    plan: list[TaskTakeoverPlanStep] = Field(default_factory=list)
    work_tree: WorkTreeProtocol | None = Field(default=None, alias="workTree")
    delivery_sections: list[TaskTakeoverDeliverySection] = Field(default_factory=list, alias="deliverySections")
    verification_items: list[TaskTakeoverVerificationItem] = Field(default_factory=list, alias="verificationItems")
    metrics: TaskTakeoverMetrics
    applied_modules: list[str] = Field(default_factory=list, alias="appliedModules")
    hook_trace: list[dict[str, Any]] = Field(default_factory=list, alias="hookTrace")


class ModelRouteDecision(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    task_id: str | None = Field(default=None, alias="taskId")
    agent_run_id: str | None = Field(default=None, alias="agentRunId")
    selected_model: str = Field(alias="selectedModel")
    selected_provider: str | None = Field(default=None, alias="selectedProvider")
    candidate_models: list[dict[str, Any]] = Field(default_factory=list, alias="candidateModels")
    reason: str
    budget_score: float = Field(alias="budgetScore")
    quality_score: float = Field(alias="qualityScore")
    latency_score: float = Field(alias="latencyScore")
    route_policy_version: str = Field(alias="routePolicyVersion")
    created_at: datetime = Field(alias="createdAt")


class WorkerActivityDescriptor(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    module_id: str = Field(alias="moduleId")
    description: str
    implementation_ref: str = Field(alias="implementationRef")
    timeout_ms: int = Field(alias="timeoutMs")
    retryable: bool = True


class PullRequestRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    project_id: str = Field(alias="projectId")
    source_branch_id: str = Field(alias="sourceBranchId")
    target_branch_id: str = Field(alias="targetBranchId")
    title: str
    summary: str
    status: Literal["open", "approved", "rejected", "merged", "closed"]
    created_by: ActorRef = Field(alias="createdBy")
    reviewed_by: ActorRef | None = Field(default=None, alias="reviewedBy")
    external_id: str | None = Field(default=None, alias="externalId")
    external_url: str | None = Field(default=None, alias="externalUrl")
    merge_commit_ref: str | None = Field(default=None, alias="mergeCommitRef")
    merged_at: datetime | None = Field(default=None, alias="mergedAt")
    created_at: datetime = Field(alias="createdAt")


class ReviewCommentRecord(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    pr_id: str = Field(alias="prId")
    author: ActorRef
    target_kind: Literal["node", "edge", "plan", "package"] = Field(alias="targetKind")
    target_id: str = Field(alias="targetId")
    body: str
    status: Literal["open", "resolved", "rejected"]
    created_at: datetime = Field(alias="createdAt")
    resolved_at: datetime | None = Field(default=None, alias="resolvedAt")


class SpecDocumentSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    name: str
    category: str
    path: str
    status: str | None = None
    version: str | None = None
    updated_at: str | None = Field(default=None, alias="updatedAt")


class ModuleCatalogSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    generated_at: datetime = Field(alias="generatedAt")
    manifests: list[ModuleManifestSummary]
    installs: list[ModuleInstallRecord]
    hooks: list[HookContributionRecord]
    subscriptions: list[EventSubscriptionRecord]
    health: list[HealthReport]


class ApplicationManifestSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    app_id: str = Field(alias="appId")
    display_name: str = Field(alias="displayName")
    version: str
    manifest_path: str = Field(alias="manifestPath")
    owner: str | None = None
    description: str | None = None
    default_load: bool = Field(default=False, alias="defaultLoad")
    module_dependencies: list[str] = Field(default_factory=list, alias="moduleDependencies")
    capability_module_ids: list[str] = Field(default_factory=list, alias="capabilityModuleIds")
    scene_module_ids: list[str] = Field(default_factory=list, alias="sceneModuleIds")
    default_prompt_profile_id: str | None = Field(default=None, alias="defaultPromptProfileId")
    subagent_prompt_profile_id: str | None = Field(default=None, alias="subagentPromptProfileId")
    default_seed_template_id: str | None = Field(default=None, alias="defaultSeedTemplateId")
    prompt_profile_files: list[str] = Field(default_factory=list, alias="promptProfileFiles")
    seed_template_files: list[str] = Field(default_factory=list, alias="seedTemplateFiles")
    config_defaults_ref: ExternalRef | None = Field(default=None, alias="configDefaultsRef")
    frontend_entry_route: str | None = Field(default=None, alias="frontendEntryRoute")
    dashboard_ref: ExternalRef | None = Field(default=None, alias="dashboardRef")


class ApplicationCatalogSnapshot(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    generated_at: datetime = Field(alias="generatedAt")
    manifests: list[ApplicationManifestSummary]


class ApplicationConfigBinding(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    app_id: str = Field(alias="appId")
    active: bool = False
    important_config: dict[str, Any] = Field(default_factory=dict, alias="importantConfig")
    updated_at: datetime = Field(alias="updatedAt")