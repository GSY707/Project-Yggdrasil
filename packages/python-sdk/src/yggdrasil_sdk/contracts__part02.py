from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .contracts__part01 import (  # noqa: F401
    _contracts_utcnow,
    _normalized_string,
    _stable_contract_digest,
    _working_node_annotation,
)
from .contracts__part01 import *  # noqa: F403,F401

class WorkContextChildCompletionSummary(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    child_node_id: str = Field(alias="childNodeId")
    status: Literal["completed", "failed"] = "completed"
    summary: str
    summary_type: Literal["execution-result", "failure-reason", "process-description"] = Field(
        default="execution-result", alias="summaryType"
    )
    evidence_refs: list[EntityRef] = Field(default_factory=list, alias="evidenceRefs")
    completed_at: datetime = Field(default_factory=_contracts_utcnow, alias="completedAt")
class WorkContextFrame(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    node_id: str = Field(alias="nodeId")
    parent_frame_id: str | None = Field(default=None, alias="parentFrameId")
    stack_depth: int = Field(alias="stackDepth")
    working_node_annotation: str = Field(alias="workingNodeAnnotation")
    entry_context_digest: str = Field(alias="entryContextDigest")
    prefix_cache_key: str | None = Field(default=None, alias="prefixCacheKey")
    frame_header: str = Field(default="", alias="frameHeader")
    frame_local_transcript_ref: EntityRef | None = Field(default=None, alias="frameLocalTranscriptRef")
    child_completion_summaries: list[WorkContextChildCompletionSummary] = Field(
        default_factory=list,
        alias="childCompletionSummaries",
    )
    cursor_state: str | None = Field(default=None, alias="cursorState")
    status: Literal["active", "suspended", "completed", "failed"] = "active"

    @model_validator(mode="before")
    @classmethod
    def _normalize_frame(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        node_id = _normalized_string(data.get("nodeId") or data.get("node_id")) or "work-tree-node"
        frame_id = _normalized_string(data.get("id")) or f"frame-{node_id}"
        data["id"] = frame_id
        data["nodeId"] = node_id
        data["stackDepth"] = int(data.get("stackDepth") or data.get("stack_depth") or 0)
        data["workingNodeAnnotation"] = (
            _normalized_string(data.get("workingNodeAnnotation") or data.get("working_node_annotation"))
            or _working_node_annotation(node_id)
            or ""
        )
        data["entryContextDigest"] = _normalized_string(data.get("entryContextDigest") or data.get("entry_context_digest")) or _stable_contract_digest(
            {"nodeId": node_id, "frameId": frame_id}
        )
        data.setdefault("frameHeader", data.get("frame_header") or data.get("workingNodeAnnotation") or data["workingNodeAnnotation"])
        data.setdefault("childCompletionSummaries", data.get("child_completion_summaries") or [])
        data["prefixCacheKey"] = _normalized_string(data.get("prefixCacheKey") or data.get("prefix_cache_key")) or build_work_context_prefix_cache_key(data)
        return data
class WorkContextStack(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version: str = "0.2.0"
    task_id: str = Field(alias="taskId")
    agent_run_id: str = Field(alias="agentRunId")
    root_frame_id: str = Field(alias="rootFrameId")
    top_frame_id: str = Field(alias="topFrameId")
    frames: list[WorkContextFrame] = Field(default_factory=list)
    cache_policy: Literal["preserve-prefix", "allow-recompile"] = Field(default="preserve-prefix", alias="cachePolicy")
    stack_digest: str = Field(alias="stackDigest")
    updated_at: datetime = Field(default_factory=_contracts_utcnow, alias="updatedAt")

    @model_validator(mode="before")
    @classmethod
    def _normalize_stack(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        frames = normalize_work_context_frames_payload(data.get("frames") or [])
        root_frame_id = _normalized_string(data.get("rootFrameId") or data.get("root_frame_id"))
        top_frame_id = _normalized_string(data.get("topFrameId") or data.get("top_frame_id"))
        if frames:
            root_frame_id = root_frame_id or _normalized_string(frames[0].get("id"))
            top_frame_id = top_frame_id or _normalized_string(frames[-1].get("id"))
        data["version"] = "0.2.0"
        data["rootFrameId"] = root_frame_id or top_frame_id or "frame-root"
        data["topFrameId"] = top_frame_id or root_frame_id or "frame-root"
        data.setdefault("cachePolicy", data.get("cache_policy") or "preserve-prefix")
        data["stackDigest"] = _normalized_string(data.get("stackDigest") or data.get("stack_digest")) or _stable_contract_digest(
            {
                "taskId": data.get("taskId") or data.get("task_id"),
                "agentRunId": data.get("agentRunId") or data.get("agent_run_id"),
                "rootFrameId": data["rootFrameId"],
                "topFrameId": data["topFrameId"],
                "frameIds": [frame.get("id") for frame in frames],
            }
        )
        data.setdefault("updatedAt", data.get("updated_at") or _contracts_utcnow())
        return data
class TaskTakeoverVerificationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    label: str
    status: Literal["passed", "warning", "failed", "not-run"]
    detail: str | None = None
    gate_mode: Literal["hard", "advisory"] = Field(default="advisory", alias="gateMode")
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
    plan_confirmation_needed: bool = Field(default=False, alias="planConfirmationNeeded")
    plan_confirmed: bool = Field(default=False, alias="planConfirmed")
    delivery_completeness_score_0_100: float = Field(default=0.0, alias="deliveryCompletenessScore0_100")
    verification_pass_rate: float = Field(default=0.0, alias="verificationPassRate")
class TaskTakeoverProtocol(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    id: str
    version: str = "0.2.0"
    task_id: str = Field(alias="taskId")
    task_type: str = Field(alias="taskType")
    run_type: str = Field(alias="runType")
    current_phase: Literal["objective", "constraints", "plan", "confirm", "execute", "verify", "deliver"] = Field(alias="currentPhase")
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

    @model_validator(mode="before")
    @classmethod
    def _backfill_work_tree_task_id(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        work_tree = data.get("workTree") if isinstance(data.get("workTree"), dict) else None
        task_id = _normalized_string(data.get("taskId") or data.get("task_id"))
        if work_tree is not None and task_id is not None and _normalized_string(work_tree.get("taskId") or work_tree.get("task_id")) is None:
            data["workTree"] = {**work_tree, "taskId": task_id}
        return data
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
    memory_namespace: str | None = Field(default=None, alias="memoryNamespace")
    memory_asset_files: list[str] = Field(default_factory=list, alias="memoryAssetFiles")
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