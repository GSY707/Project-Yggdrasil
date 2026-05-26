from __future__ import annotations

from datetime import datetime, timezone
import json
from hashlib import sha256
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


def _contracts_utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalized_string(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalized_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        candidates = [values]
    elif isinstance(values, (list, tuple, set)):
        candidates = list(values)
    else:
        candidates = [values]
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in candidates:
        normalized = _normalized_string(value)
        if normalized is None or normalized in seen:
            continue
        seen.add(normalized)
        normalized_values.append(normalized)
    return normalized_values


def _stable_contract_digest(payload: Any) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(serialized.encode("utf-8")).hexdigest()[:16]


def _normalized_child_completion_payloads(values: Any) -> list[dict[str, Any]]:
    normalized_payloads: list[dict[str, Any]] = []
    for item in values or []:
        payload = _raw_work_tree_node_payload(item)
        child_node_id = _normalized_string(payload.get("childNodeId") or payload.get("child_node_id"))
        if child_node_id is None:
            continue
        normalized_payloads.append(
            {
                "childNodeId": child_node_id,
                "status": _normalized_string(payload.get("status")) or "completed",
                "summary": _normalized_string(payload.get("summary")) or "",
            }
        )
    return normalized_payloads


def build_work_context_prefix_cache_key(
    frame: Any,
    *,
    parent_prefix_cache_key: str | None = None,
) -> str:
    payload = _raw_work_tree_node_payload(frame)
    node_id = _normalized_string(payload.get("nodeId") or payload.get("node_id")) or "work-tree-node"
    frame_id = _normalized_string(payload.get("id")) or f"frame-{node_id}"
    working_node_annotation = (
        _normalized_string(payload.get("workingNodeAnnotation") or payload.get("working_node_annotation"))
        or _working_node_annotation(node_id)
        or ""
    )
    entry_context_digest = _normalized_string(payload.get("entryContextDigest") or payload.get("entry_context_digest")) or _stable_contract_digest(
        {"nodeId": node_id, "frameId": frame_id}
    )
    return _stable_contract_digest(
        {
            "frameId": frame_id,
            "nodeId": node_id,
            "parentFrameId": _normalized_string(payload.get("parentFrameId") or payload.get("parent_frame_id")),
            "stackDepth": int(payload.get("stackDepth") or payload.get("stack_depth") or 0),
            "workingNodeAnnotation": working_node_annotation,
            "entryContextDigest": entry_context_digest,
            "frameHeader": _normalized_string(payload.get("frameHeader") or payload.get("frame_header")) or "",
            "cursorState": _normalized_string(payload.get("cursorState") or payload.get("cursor_state")),
            "childCompletionSummaries": _normalized_child_completion_payloads(
                payload.get("childCompletionSummaries") or payload.get("child_completion_summaries") or []
            ),
            "parentPrefixCacheKey": _normalized_string(parent_prefix_cache_key),
        }
    )


def normalize_work_context_frames_payload(frames: list[Any] | None) -> list[dict[str, Any]]:
    normalized_frames: list[dict[str, Any]] = []
    parent_frame_id: str | None = None
    parent_prefix_cache_key: str | None = None
    for depth, frame in enumerate(frames or []):
        payload = _raw_work_tree_node_payload(frame)
        node_id = _normalized_string(payload.get("nodeId") or payload.get("node_id")) or "work-tree-node"
        frame_id = _normalized_string(payload.get("id")) or f"frame-{node_id}"
        normalized_payload: dict[str, Any] = {
            **payload,
            "id": frame_id,
            "nodeId": node_id,
            "parentFrameId": parent_frame_id,
            "stackDepth": depth,
            "workingNodeAnnotation": (
                _normalized_string(payload.get("workingNodeAnnotation") or payload.get("working_node_annotation"))
                or _working_node_annotation(node_id)
                or ""
            ),
            "entryContextDigest": _normalized_string(payload.get("entryContextDigest") or payload.get("entry_context_digest")) or _stable_contract_digest(
                {"nodeId": node_id, "frameId": frame_id}
            ),
            "frameHeader": _normalized_string(payload.get("frameHeader") or payload.get("frame_header"))
            or _normalized_string(payload.get("workingNodeAnnotation") or payload.get("working_node_annotation"))
            or _working_node_annotation(node_id)
            or "",
            "childCompletionSummaries": payload.get("childCompletionSummaries") or payload.get("child_completion_summaries") or [],
            "cursorState": _normalized_string(payload.get("cursorState") or payload.get("cursor_state")),
            "status": _normalized_string(payload.get("status")) or "active",
        }
        if payload.get("frameLocalTranscriptRef") is not None or payload.get("frame_local_transcript_ref") is not None:
            normalized_payload["frameLocalTranscriptRef"] = payload.get("frameLocalTranscriptRef") or payload.get("frame_local_transcript_ref")
        normalized_payload["prefixCacheKey"] = build_work_context_prefix_cache_key(
            normalized_payload,
            parent_prefix_cache_key=parent_prefix_cache_key,
        )
        normalized_frames.append(normalized_payload)
        parent_frame_id = frame_id
        parent_prefix_cache_key = normalized_payload["prefixCacheKey"]
    return normalized_frames


def _working_node_annotation(node_id: Any) -> str | None:
    normalized = _normalized_string(node_id)
    if normalized is None:
        return None
    return f"<Working_Node: {normalized}>"


def _raw_work_tree_node_payload(node: Any) -> dict[str, Any]:
    if isinstance(node, dict):
        return dict(node)
    if hasattr(node, "model_dump"):
        return node.model_dump(by_alias=True, mode="json")
    return {}


def _preferred_work_tree_node_id(nodes: list[Any]) -> str | None:
    normalized_nodes = [_raw_work_tree_node_payload(node) for node in nodes]
    executable_nodes = [
        payload
        for payload in normalized_nodes
        if not (
            len(normalized_nodes) > 1
            and _normalized_string(payload.get("parentNodeId") or payload.get("parent_node_id")) is None
            and bool(payload.get("childNodeIds") or payload.get("child_node_ids"))
        )
    ]
    if not executable_nodes:
        executable_nodes = normalized_nodes
    for preferred_status in ("in-progress", "blocked", "pending", "summarizing"):
        for payload in executable_nodes:
            if str(payload.get("status") or "") == preferred_status:
                return _normalized_string(payload.get("id"))
    for payload in executable_nodes:
        status = str(payload.get("status") or "")
        if status not in {"completed", "skipped", "failed"}:
            return _normalized_string(payload.get("id"))
    for payload in reversed(executable_nodes):
        candidate = _normalized_string(payload.get("id"))
        if candidate is not None:
            return candidate
    return None


def _build_active_path_node_ids(nodes: list[Any], *, current_node_id: str | None, root_node_id: str | None) -> list[str]:
    if current_node_id is None and root_node_id is None:
        return []
    parent_lookup: dict[str, str | None] = {}
    for node in nodes:
        payload = _raw_work_tree_node_payload(node)
        node_id = _normalized_string(payload.get("id"))
        if node_id is None:
            continue
        parent_lookup[node_id] = _normalized_string(payload.get("parentNodeId") or payload.get("parent_node_id"))
    path: list[str] = []
    cursor = current_node_id or root_node_id
    seen: set[str] = set()
    while cursor is not None and cursor not in seen:
        seen.add(cursor)
        path.append(cursor)
        cursor = parent_lookup.get(cursor)
    path.reverse()
    if root_node_id is not None and (not path or path[0] != root_node_id):
        path.insert(0, root_node_id)
    return _normalized_string_list(path)


def _work_tree_protocol_id(task_id: str | None, root_node_id: str | None, root_objective: str) -> str:
    if task_id is not None:
        return f"work-tree-{task_id}"
    if root_node_id is not None:
        return f"work-tree-{root_node_id}"
    return f"work-tree-{_stable_contract_digest({'rootObjective': root_objective})}"


def _first_request_state(actions: Any) -> dict[str, Any]:
    if not isinstance(actions, list):
        return {}
    for action in actions:
        if not isinstance(action, dict):
            continue
        request_state = action.get("requestState")
        if isinstance(request_state, dict):
            return request_state
    return {}


def _runtime_pointer_from_request_state(request_state: dict[str, Any]) -> dict[str, str | None]:
    takeover_protocol = request_state.get("takeoverProtocol") if isinstance(request_state.get("takeoverProtocol"), dict) else {}
    work_tree = takeover_protocol.get("workTree") if isinstance(takeover_protocol.get("workTree"), dict) else {}
    work_context_stack = request_state.get("workContextStack") if isinstance(request_state.get("workContextStack"), dict) else {}
    memory_retrieval_state = request_state.get("memoryRetrievalState") if isinstance(request_state.get("memoryRetrievalState"), dict) else {}

    current_node_id = _normalized_string(
        request_state.get("currentNodeId")
        or work_tree.get("currentNodeId")
        or memory_retrieval_state.get("workTreeNodeId")
    )
    working_node_annotation = _normalized_string(
        request_state.get("workingNodeAnnotation")
        or work_tree.get("workingNodeAnnotation")
        or _working_node_annotation(current_node_id)
    )
    pc_memo = _normalized_string(request_state.get("pcMemo") or work_tree.get("pcMemo"))
    top_frame_id = _normalized_string(work_context_stack.get("topFrameId") or request_state.get("topFrameId"))
    if top_frame_id is None and current_node_id is not None:
        top_frame_id = f"frame-{current_node_id}"
    stack_digest = _normalized_string(work_context_stack.get("stackDigest") or request_state.get("stackDigest"))
    if stack_digest is None and current_node_id is not None:
        stack_digest = _stable_contract_digest(
            {
                "currentNodeId": current_node_id,
                "topFrameId": top_frame_id,
                "workingNodeAnnotation": working_node_annotation,
            }
        )
    return {
        "currentNodeId": current_node_id,
        "workingNodeAnnotation": working_node_annotation,
        "pcMemo": pc_memo,
        "topFrameId": top_frame_id,
        "stackDigest": stack_digest,
    }


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


class BudgetCheckResult(BaseModel):
    """Result of pre-invocation budget check."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    check_passed: bool = Field(alias="checkPassed")
    reason: str | None = None
    available_token_budget: int = Field(alias="availableTokenBudget")
    available_cost_budget: float = Field(alias="availableCostBudget")
    estimated_total_tokens: int = Field(alias="estimatedTotalTokens")
    estimated_cost: float = Field(alias="estimatedCost")


class BudgetOverrunResult(BaseModel):
    """Result of post-invocation budget validation."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    is_overrun: bool = Field(alias="isOverrun")
    violation_type: Literal["token", "cost", "both"] | None = Field(
        default=None, alias="violationType"
    )
    tokens_used: int = Field(alias="tokensUsed")
    cost_used: float = Field(alias="costUsed")
    tokens_exceeded_by: int = Field(alias="tokensExceededBy")
    cost_exceeded_by: float = Field(alias="costExceededBy")


class ToolExecutionFailure(BaseModel):
    """Record of a tool execution failure with retry information."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tool_name: str = Field(alias="toolName")
    error_message: str = Field(alias="errorMessage")
    error_type: str = Field(alias="errorType")
    retry_count: int = Field(default=0, alias="retryCount")
    is_retryable: bool = Field(alias="isRetryable")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ToolExecutionResult(BaseModel):
    """Detailed result of a single tool execution."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    tool_name: str = Field(alias="toolName")
    tool_call_id: str = Field(alias="toolCallId")
    success: bool
    result: dict[str, Any] = Field(default_factory=dict)
    failure: ToolExecutionFailure | None = None
    duration_ms: int = Field(alias="durationMs")


class RuntimeMetricsSnapshot(BaseModel):
    """Snapshot of runtime metrics at a specific point in execution."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    window_index: int = Field(alias="windowIndex")
    restart_count: int = Field(alias="restartCount")
    total_tokens_used: int = Field(alias="totalTokensUsed")
    total_cost_used: float = Field(alias="totalCostUsed")
    cache_hit_input_tokens: int = Field(default=0, alias="cacheHitInputTokens")
    cache_write_input_tokens: int = Field(default=0, alias="cacheWriteInputTokens")
    non_cache_input_tokens: int = Field(default=0, alias="nonCacheInputTokens")
    cumulative_window_span_tokens: int = Field(alias="cumulativeWindowSpanTokens")
    carry_forward_loss_count: int = Field(alias="carryForwardLossCount")
    tool_round_count: int = Field(alias="toolRoundCount")
    tool_failures_count: int = Field(alias="toolFailuresCount")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class RuntimeMetricsArtifact(BaseModel):
    """Persistent artifact storing runtime metrics across windows."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    artifact_id: str = Field(alias="artifactId")
    task_id: str = Field(alias="taskId")
    run_id: str = Field(alias="runId")
    invocation_id: str = Field(alias="invocationId")
    snapshots: list[RuntimeMetricsSnapshot] = Field(default_factory=list)
    cumulative_tokens: int = Field(alias="cumulativeTokens")
    cumulative_cost: float = Field(alias="cumulativeCost")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SnapshotIntegrityCheck(BaseModel):
    """Integrity check information for snapshot verification."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    checksum: str
    checksum_algorithm: str = Field(default="sha256", alias="checksumAlgorithm")
    verified_at: datetime = Field(default_factory=datetime.utcnow)
    is_valid: bool = True


class PendingActionSnapshot(BaseModel):
    """Restorable pending action with deterministic integrity checksum."""
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    kind: str
    payload: dict[str, Any] = Field(default_factory=dict)
    checksum: str
    checksum_algorithm: str = Field(default="sha256", alias="checksumAlgorithm")
    checksum_verified_at: datetime | None = Field(default=None, alias="checksumVerifiedAt")
    checksum_failed: bool = Field(default=False, alias="checksumFailed")
    failure_reason: str | None = Field(default=None, alias="failureReason")


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
    semantic_roots: dict[str, Any] = Field(default_factory=dict, alias="semanticRoots")
    system_root_protocol: dict[str, Any] = Field(default_factory=dict, alias="systemRootProtocol")
    capability_index: list[dict[str, Any]] = Field(default_factory=list, alias="capabilityIndex")
    tool_index: list[dict[str, Any]] = Field(default_factory=list, alias="toolIndex")
    startup_load_order: list[str] = Field(default_factory=list, alias="startupLoadOrder")
    startup_mode: Literal["standby", "resume-node", "bootstrap"] = Field(default="bootstrap", alias="startupMode")
    mailbox_state: dict[str, Any] = Field(default_factory=dict, alias="mailboxState")
    standby_state: dict[str, Any] = Field(default_factory=dict, alias="standbyState")
    current_node_id: str | None = Field(default=None, alias="currentNodeId")
    working_node_annotation: str | None = Field(default=None, alias="workingNodeAnnotation")
    pc_memo: str | None = Field(default=None, alias="pcMemo")
    top_frame_id: str | None = Field(default=None, alias="topFrameId")
    stack_digest: str | None = Field(default=None, alias="stackDigest")
    generated_at: datetime = Field(alias="generatedAt")


class TaskRuntimeState(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    task_id: str | None = Field(default=None, alias="taskId")
    phase: Literal["start-state", "task-state-loaded", "lossless-restore"] | None = Field(default=None, alias="phase")
    task_objective: str | None = Field(default=None, alias="taskObjective")
    current_focus: str | None = Field(default=None, alias="currentFocus")
    current_node_id: str | None = Field(default=None, alias="currentNodeId")
    working_node_annotation: str | None = Field(default=None, alias="workingNodeAnnotation")
    pc_memo: str | None = Field(default=None, alias="pcMemo")
    resume_message: str | None = Field(default=None, alias="resumeMessage")
    restart_message: str | None = Field(default=None, alias="restartMessage")
    takeover_protocol: TaskTakeoverProtocol | None = Field(default=None, alias="takeoverProtocol")
    work_context_stack: WorkContextStack | None = Field(default=None, alias="workContextStack")
    memory_retrieval_state: dict[str, Any] | None = Field(default=None, alias="memoryRetrievalState")
    budget_state: BudgetState | None = Field(default=None, alias="budgetState")


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
    current_node_id: str | None = Field(default=None, alias="currentNodeId")
    working_node_annotation: str | None = Field(default=None, alias="workingNodeAnnotation")
    pc_memo: str | None = Field(default=None, alias="pcMemo")
    top_frame_id: str | None = Field(default=None, alias="topFrameId")
    stack_digest: str | None = Field(default=None, alias="stackDigest")
    blockers: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _backfill_runtime_pointer_fields(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        pointer = _runtime_pointer_from_request_state(
            _first_request_state(data.get("pendingActions") or data.get("pending_actions"))
        )
        if _normalized_string(data.get("currentNodeId") or data.get("current_node_id")) is None and pointer["currentNodeId"] is not None:
            data["currentNodeId"] = pointer["currentNodeId"]
        current_node_id = _normalized_string(data.get("currentNodeId") or data.get("current_node_id"))
        if _normalized_string(data.get("workingNodeAnnotation") or data.get("working_node_annotation")) is None:
            data["workingNodeAnnotation"] = pointer["workingNodeAnnotation"] or _working_node_annotation(current_node_id)
        if _normalized_string(data.get("pcMemo") or data.get("pc_memo")) is None and pointer["pcMemo"] is not None:
            data["pcMemo"] = pointer["pcMemo"]
        if _normalized_string(data.get("topFrameId") or data.get("top_frame_id")) is None and pointer["topFrameId"] is not None:
            data["topFrameId"] = pointer["topFrameId"]
        if _normalized_string(data.get("stackDigest") or data.get("stack_digest")) is None and pointer["stackDigest"] is not None:
            data["stackDigest"] = pointer["stackDigest"]
        return data


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
    parent_node_id: str | None = Field(default=None, alias="parentNodeId")
    questions_it_answers: list[str] = Field(default_factory=list, alias="questionsItAnswers")
    node_text: str = Field(default="", alias="nodeText")
    local_goal: str = Field(default="", alias="localGoal")
    local_constraints: list[str] = Field(default_factory=list, alias="localConstraints")
    local_context_refs: list[EntityRef] = Field(default_factory=list, alias="localContextRefs")
    working_node_annotation: str = Field(default="", alias="workingNodeAnnotation")
    execution_summary: str | None = Field(default=None, alias="executionSummary")
    failure_summary: str | None = Field(default=None, alias="failureSummary")
    phase: Literal["planning", "executing", "recovering", "restarting", "verification", "delivery", "standby", "coordination"]
    status: Literal["pending", "in-progress", "summarizing", "completed", "failed", "blocked", "skipped"] = "pending"
    child_node_ids: list[str] = Field(default_factory=list, alias="childNodeIds")
    plan_step_ids: list[str] = Field(default_factory=list, alias="planStepIds")
    constraint_ids: list[str] = Field(default_factory=list, alias="constraintIds")
    depends_on: list[str] = Field(default_factory=list, alias="dependsOn")
    relation_ids: list[str] = Field(default_factory=list, alias="relationIds")
    expected_evidence: list[str] = Field(default_factory=list, alias="expectedEvidence")
    produced_evidence_refs: list[EntityRef] = Field(default_factory=list, alias="producedEvidenceRefs")
    source_memory_node_ids: list[str] = Field(default_factory=list, alias="sourceMemoryNodeIds")
    assigned_agent_run_id: str | None = Field(default=None, alias="assignedAgentRunId")
    owner_agent_id: str | None = Field(default=None, alias="ownerAgentId")
    priority: int = 100
    detail_level: int = Field(default=0, alias="detailLevel")
    version: int = 1
    created_at: datetime = Field(default_factory=_contracts_utcnow, alias="createdAt")
    updated_at: datetime = Field(default_factory=_contracts_utcnow, alias="updatedAt")
    recovery_anchor: str | None = Field(default=None, alias="recoveryAnchor")

    @model_validator(mode="before")
    @classmethod
    def _upgrade_v0_1_payload(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        node_id = _normalized_string(data.get("id")) or "work-tree-node"
        title = _normalized_string(data.get("title")) or node_id
        local_goal = _normalized_string(data.get("localGoal") or data.get("local_goal")) or title
        data["id"] = node_id
        data["title"] = title
        data["questionsItAnswers"] = _normalized_string_list(
            data.get("questionsItAnswers") or data.get("questions_it_answers") or [title]
        )
        data["nodeText"] = _normalized_string(data.get("nodeText") or data.get("node_text")) or local_goal
        data["localGoal"] = local_goal
        data["localConstraints"] = _normalized_string_list(
            data.get("localConstraints") or data.get("local_constraints") or data.get("constraintIds")
        )
        data.setdefault("localContextRefs", data.get("local_context_refs") or [])
        data["workingNodeAnnotation"] = (
            _normalized_string(data.get("workingNodeAnnotation") or data.get("working_node_annotation"))
            or _working_node_annotation(node_id)
            or ""
        )
        data["childNodeIds"] = _normalized_string_list(data.get("childNodeIds") or data.get("child_node_ids"))
        data["planStepIds"] = _normalized_string_list(data.get("planStepIds") or data.get("plan_step_ids"))
        data["constraintIds"] = _normalized_string_list(data.get("constraintIds") or data.get("constraint_ids"))
        data["dependsOn"] = _normalized_string_list(data.get("dependsOn") or data.get("depends_on"))
        data["relationIds"] = _normalized_string_list(data.get("relationIds") or data.get("relation_ids"))
        data["expectedEvidence"] = _normalized_string_list(data.get("expectedEvidence") or data.get("expected_evidence"))
        data.setdefault("producedEvidenceRefs", data.get("produced_evidence_refs") or [])
        data["sourceMemoryNodeIds"] = _normalized_string_list(
            data.get("sourceMemoryNodeIds") or data.get("source_memory_node_ids")
        )
        data["priority"] = int(data.get("priority") or 100)
        data["detailLevel"] = int(data.get("detailLevel") or data.get("detail_level") or 0)
        data["version"] = int(data.get("version") or 1)
        data.setdefault("createdAt", data.get("created_at") or _contracts_utcnow())
        data.setdefault("updatedAt", data.get("updated_at") or data.get("createdAt") or _contracts_utcnow())
        return data


class WorkTreeProtocol(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    version: str = "0.2.0"
    id: str
    task_id: str | None = Field(default=None, alias="taskId")
    root_node_id: str | None = Field(default=None, alias="rootNodeId")
    root_objective: str = Field(alias="rootObjective")
    status: Literal[
        "planned",
        "standby",
        "active",
        "summarizing",
        "recovering",
        "restarting",
        "paused",
        "verified",
        "awaiting-approval",
        "completed",
        "failed",
    ]
    current_node_id: str | None = Field(default=None, alias="currentNodeId")
    nodes: list[WorkTreeNode] = Field(default_factory=list)
    loaded_node_ids: list[str] = Field(default_factory=list, alias="loadedNodeIds")
    active_path_node_ids: list[str] = Field(default_factory=list, alias="activePathNodeIds")
    index_map_refs: list[EntityRef] = Field(default_factory=list, alias="indexMapRefs")
    pc_memo: str | None = Field(default=None, alias="pcMemo")
    recovery_anchor: str | None = Field(default=None, alias="recoveryAnchor")
    entropy_budget_remaining: int = Field(default=0, alias="entropyBudgetRemaining")
    version_counter: int = Field(default=1, alias="versionCounter")
    updated_at: datetime = Field(default_factory=_contracts_utcnow, alias="updatedAt")

    @model_validator(mode="before")
    @classmethod
    def _upgrade_v0_1_payload(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value
        data = dict(value or {})
        root_objective = _normalized_string(data.get("rootObjective") or data.get("root_objective")) or "Unknown objective"
        task_id = _normalized_string(data.get("taskId") or data.get("task_id"))
        nodes = [_raw_work_tree_node_payload(node) for node in data.get("nodes") or []]
        current_node_id = _normalized_string(data.get("currentNodeId") or data.get("current_node_id"))
        recovery_anchor = _normalized_string(data.get("recoveryAnchor") or data.get("recovery_anchor"))

        if task_id is not None and current_node_id is None:
            current_node_id = _preferred_work_tree_node_id(nodes)

        root_node_id = _normalized_string(data.get("rootNodeId") or data.get("root_node_id"))
        has_parent_links = any(
            _normalized_string(node.get("parentNodeId") or node.get("parent_node_id")) is not None
            for node in nodes
        )
        explicit_root_only = bool(
            root_node_id is not None
            and len(nodes) == 1
            and _normalized_string(nodes[0].get("id")) == root_node_id
            and _normalized_string(nodes[0].get("parentNodeId") or nodes[0].get("parent_node_id")) is None
        )
        if not explicit_root_only and len(nodes) == 1:
            only_node_id = _normalized_string(nodes[0].get("id"))
            only_parent_id = _normalized_string(nodes[0].get("parentNodeId") or nodes[0].get("parent_node_id"))
            if only_node_id is not None and only_parent_id is None:
                root_node_id = root_node_id or only_node_id
                explicit_root_only = True
        if not nodes:
            root_node_id = root_node_id or f"{_work_tree_protocol_id(task_id, None, root_objective)}-root"
            current_node_id = current_node_id or root_node_id
            nodes = [
                {
                    "id": root_node_id,
                    "parentNodeId": None,
                    "title": "Establish executable plan",
                    "questionsItAnswers": [root_objective],
                    "nodeText": root_objective,
                    "localGoal": root_objective,
                    "localConstraints": [],
                    "localContextRefs": [],
                    "workingNodeAnnotation": _working_node_annotation(root_node_id),
                    "executionSummary": None,
                    "failureSummary": None,
                    "phase": "planning",
                    "status": "in-progress",
                    "childNodeIds": [],
                    "planStepIds": [],
                    "constraintIds": [],
                    "dependsOn": [],
                    "relationIds": [],
                    "expectedEvidence": ["normalized objective", "constraint baseline"],
                    "producedEvidenceRefs": [],
                    "sourceMemoryNodeIds": [],
                    "priority": 0,
                    "detailLevel": 0,
                    "version": 1,
                    "recoveryAnchor": recovery_anchor or "resume:bootstrap",
                    "createdAt": _contracts_utcnow(),
                    "updatedAt": _contracts_utcnow(),
                }
            ]
        elif not explicit_root_only and (root_node_id is None or not has_parent_links):
            root_node_id = root_node_id or f"{_work_tree_protocol_id(task_id, None, root_objective)}-root"
            child_node_ids: list[str] = []
            normalized_nodes: list[dict[str, Any]] = []
            for node in nodes:
                node_id = _normalized_string(node.get("id"))
                if node_id is None:
                    continue
                child_node_ids.append(node_id)
                if _normalized_string(node.get("parentNodeId") or node.get("parent_node_id")) is None:
                    node["parentNodeId"] = root_node_id
                node.setdefault("detailLevel", 1)
                normalized_nodes.append(node)
            nodes = [
                {
                    "id": root_node_id,
                    "parentNodeId": None,
                    "title": "Task root",
                    "questionsItAnswers": [root_objective],
                    "nodeText": root_objective,
                    "localGoal": root_objective,
                    "localConstraints": [],
                    "localContextRefs": [],
                    "workingNodeAnnotation": _working_node_annotation(root_node_id),
                    "executionSummary": None,
                    "failureSummary": None,
                    "phase": "planning",
                    "status": "in-progress",
                    "childNodeIds": child_node_ids,
                    "planStepIds": [],
                    "constraintIds": [],
                    "dependsOn": [],
                    "relationIds": [],
                    "expectedEvidence": [],
                    "producedEvidenceRefs": [],
                    "sourceMemoryNodeIds": [],
                    "priority": 0,
                    "detailLevel": 0,
                    "version": 1,
                    "recoveryAnchor": recovery_anchor,
                    "createdAt": _contracts_utcnow(),
                    "updatedAt": _contracts_utcnow(),
                },
                *normalized_nodes,
            ]

        if task_id is not None and current_node_id is None and str(data.get("status") or "") not in {"standby", "completed", "failed"}:
            current_node_id = _preferred_work_tree_node_id(nodes)
        loaded_node_ids = _normalized_string_list(
            data.get("loadedNodeIds") or data.get("loaded_node_ids") or [node.get("id") for node in nodes]
        )
        active_path_node_ids = _normalized_string_list(data.get("activePathNodeIds") or data.get("active_path_node_ids"))
        if not active_path_node_ids:
            active_path_node_ids = _build_active_path_node_ids(
                nodes,
                current_node_id=current_node_id,
                root_node_id=root_node_id,
            )
        protocol_id = _normalized_string(data.get("id")) or _work_tree_protocol_id(task_id, root_node_id, root_objective)
        status = _normalized_string(data.get("status")) or "planned"
        if status == "executing":
            status = "active"

        data.update(
            {
                "version": "0.2.0",
                "id": protocol_id,
                "taskId": task_id,
                "rootNodeId": root_node_id,
                "rootObjective": root_objective,
                "status": status,
                "currentNodeId": current_node_id,
                "nodes": nodes,
                "loadedNodeIds": loaded_node_ids,
                "activePathNodeIds": active_path_node_ids,
                "indexMapRefs": data.get("indexMapRefs") or data.get("index_map_refs") or [],
                "pcMemo": _normalized_string(data.get("pcMemo") or data.get("pc_memo")),
                "recoveryAnchor": recovery_anchor,
                "entropyBudgetRemaining": int(data.get("entropyBudgetRemaining") or data.get("entropy_budget_remaining") or 0),
                "versionCounter": int(data.get("versionCounter") or data.get("version_counter") or 1),
                "updatedAt": data.get("updatedAt") or data.get("updated_at") or _contracts_utcnow(),
            }
        )
        return data

    @model_validator(mode="after")
    def _sync_runtime_pointer_fields(self) -> "WorkTreeProtocol":
        if self.task_id is not None and self.current_node_id is None and self.status not in {"standby", "completed", "failed"}:
            self.current_node_id = _preferred_work_tree_node_id(self.nodes)
        if self.root_node_id is None and self.nodes:
            self.root_node_id = self.nodes[0].id
        if not self.loaded_node_ids:
            self.loaded_node_ids = [node.id for node in self.nodes]
        if not self.active_path_node_ids:
            self.active_path_node_ids = _build_active_path_node_ids(
                self.nodes,
                current_node_id=self.current_node_id,
                root_node_id=self.root_node_id,
            )
        if self.recovery_anchor is None and self.current_node_id is not None:
            current_node = next((node for node in self.nodes if node.id == self.current_node_id), None)
            if current_node is not None:
                self.recovery_anchor = current_node.recovery_anchor
        return self


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