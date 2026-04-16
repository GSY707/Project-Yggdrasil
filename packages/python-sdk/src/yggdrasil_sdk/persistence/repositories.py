from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from ..contracts import (
    ActorRef,
    BudgetState,
    EntityRef,
    ModuleConfigBinding,
    EventSubscriptionRecord,
    EventEnvelope,
    EventHandlingResult,
    ExternalRef,
    HealthReport,
    HookContributionRecord,
    ModelRouteDecision,
    ModuleCatalogSnapshot,
    ModuleInstallRecord,
    ModuleManifestSummary,
    PullRequestRecord,
    ReviewCommentRecord,
    TaskSnapshotSummary,
)
from ..domain import (
    AgentRunRecord,
    EdgeRecord,
    ImportFragmentRecord,
    ImportJobRecord,
    ImportPolicy,
    MemoryBranchRecord,
    NodeRecord,
    NodeVersionRecord,
    OutboxRecord,
    ProjectRecord,
    RetrievalBundle,
    RetrievalRequestRecord,
    SourceAnnotationRecord,
    SpaceRecord,
    TaskRecord,
    TreePlanRecord,
)
from ..support import new_id, utc_now
from .constants import (
    DEFAULT_BRANCH_ID,
    DEFAULT_OWNER_PROFILE_ID,
    DEFAULT_PROJECT_ID,
    DEFAULT_SPACE_ID,
    ROOT_BRANCH_CONTENTS,
    ROOT_BRANCH_TITLES,
)
from .orm import (
    AgentRunORM,
    EdgeORM,
    EventSubscriptionORM,
    HealthReportORM,
    HookContributionORM,
    ImportFragmentORM,
    ImportJobORM,
    MemoryBranchORM,
    ModelRouteDecisionORM,
    ModuleConfigBindingORM,
    ModuleInstallORM,
    NodeORM,
    NodeVersionORM,
    OutboxRecordORM,
    ProjectORM,
    RetrievalRequestORM,
    PullRequestORM,
    ReviewCommentORM,
    SourceAnnotationORM,
    SpaceORM,
    TaskORM,
    TaskSnapshotORM,
    TreePlanORM,
)


def _actor(value: dict[str, Any] | ActorRef | None, *, default_type: str = "system", default_id: str = "kernel") -> ActorRef:
    if value is None:
        return ActorRef(type=default_type, id=default_id)
    if isinstance(value, ActorRef):
        return value
    return ActorRef.model_validate(value)


def _external_ref(value: dict[str, Any] | ExternalRef | None) -> ExternalRef | None:
    if value is None:
        return None
    if isinstance(value, ExternalRef):
        return value
    return ExternalRef.model_validate(value)


def _entity_refs(values: list[dict[str, Any] | EntityRef] | None) -> list[EntityRef]:
    if not values:
        return []
    refs: list[EntityRef] = []
    for value in values:
        if isinstance(value, EntityRef):
            refs.append(value)
            continue
        refs.append(EntityRef.model_validate(value))
    return refs


def _import_policy(value: dict[str, Any] | ImportPolicy | None) -> ImportPolicy:
    if value is None:
        return ImportPolicy()
    if isinstance(value, ImportPolicy):
        return value
    return ImportPolicy.model_validate(value)


def _score_snapshot_from_node(node: NodeORM) -> dict[str, float]:
    return {
        "importance": node.importance,
        "stability": node.stability,
        "forgetRate": node.forget_rate,
        "feedforwardScore": node.feedforward_score,
        "accessScore": node.access_score,
        "activityK": node.activity_k,
        "floatScore": node.float_score,
    }


def _project_record(model: ProjectORM) -> ProjectRecord:
    return ProjectRecord(
        id=model.id,
        displayName=model.display_name,
        status=model.status,
        exportPolicy=model.export_policy,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )


def _space_record(model: SpaceORM) -> SpaceRecord:
    return SpaceRecord(
        id=model.id,
        projectId=model.project_id,
        spaceType=model.space_type,
        status=model.status,
        ownerSubject=model.owner_subject,
        createdAt=model.created_at,
    )


def _branch_record(model: MemoryBranchORM) -> MemoryBranchRecord:
    return MemoryBranchRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        name=model.name,
        baseBranchId=model.base_branch_id,
        headRef=model.head_ref,
        status=model.status,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )


def _node_record(model: NodeORM) -> NodeRecord:
    return NodeRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        branchId=model.branch_id,
        parentId=model.parent_id,
        rootBranch=model.root_branch,
        nodeType=model.node_type,
        status=model.status,
        title=model.title,
        content=model.content,
        detailLevel=model.detail_level,
        importance=model.importance,
        stability=model.stability,
        forgetRate=model.forget_rate,
        feedforwardScore=model.feedforward_score,
        accessScore=model.access_score,
        activityK=model.activity_k,
        floatScore=model.float_score,
        latestVersionId=model.latest_version_id,
        mergedIntoNodeId=model.merged_into_node_id,
        childrenCount=model.children_count,
        edgeCount=model.edge_count,
        treePath=model.tree_path,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
        updatedAt=model.updated_at,
        updatedBy=_actor(model.updated_by),
    )


def _edge_record(model: EdgeORM) -> EdgeRecord:
    return EdgeRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        branchId=model.branch_id,
        fromNodeId=model.from_node_id,
        toNodeId=model.to_node_id,
        relationType=model.relation_type,
        weight=model.weight,
        reason=model.reason,
        evidenceAnnotationIds=list(model.evidence_annotation_ids or []),
        status=model.status,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
        updatedAt=model.updated_at,
        updatedBy=_actor(model.updated_by),
    )


def _node_version_record(model: NodeVersionORM) -> NodeVersionRecord:
    return NodeVersionRecord(
        id=model.id,
        nodeId=model.node_id,
        versionNo=model.version_no,
        titleSnapshot=model.title_snapshot,
        contentSnapshot=model.content_snapshot,
        parentIdSnapshot=model.parent_id_snapshot,
        scoreSnapshot=dict(model.score_snapshot or {}),
        changeReason=model.change_reason,
        derivedFromVersionId=model.derived_from_version_id,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )


def _source_annotation_record(model: SourceAnnotationORM) -> SourceAnnotationRecord:
    return SourceAnnotationRecord(
        id=model.id,
        projectId=model.project_id,
        branchId=model.branch_id,
        ownerKind=model.owner_kind,
        ownerId=model.owner_id,
        sourceType=model.source_type,
        sourceRef=_external_ref(model.source_ref),
        excerpt=model.excerpt,
        inferenceSummary=model.inference_summary,
        evidenceRefs=_entity_refs(model.evidence_refs or []),
        confidence=model.confidence,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )


def _retrieval_request_record(model: RetrievalRequestORM) -> RetrievalRequestRecord:
    return RetrievalRequestRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        branchId=model.branch_id,
        queryText=model.query_text,
        seedNodeRefs=_entity_refs(model.seed_node_refs or []),
        traversalStart=model.traversal_start,
        expansionMode=model.expansion_mode,
        readDepth=model.read_depth,
        lateralHops=model.lateral_hops,
        maxRelatedNodes=model.max_related_nodes,
        maxLeafNodes=model.max_leaf_nodes,
        precisionMode=model.precision_mode,
        includeNaturalLanguageSummary=model.include_natural_language_summary,
        includeChildNames=model.include_child_names,
        includeRelatedNames=model.include_related_names,
        tokenBudget=model.token_budget,
        createdAt=model.created_at,
    )


def _import_job_record(model: ImportJobORM) -> ImportJobRecord:
    return ImportJobRecord(
        id=model.id,
        projectId=model.project_id,
        branchId=model.branch_id,
        sourceKind=model.source_kind,
        status=model.status,
        importPolicy=_import_policy(model.import_policy),
        requestedBy=_actor(model.requested_by),
        tokenBudget=model.token_budget,
        costBudget=model.cost_budget,
        failureReason=model.failure_reason,
        startedAt=model.started_at,
        finishedAt=model.finished_at,
        createdAt=model.created_at,
    )


def _import_fragment_record(model: ImportFragmentORM) -> ImportFragmentRecord:
    return ImportFragmentRecord(
        id=model.id,
        importJobId=model.import_job_id,
        ordinal=model.ordinal,
        rawRef=_external_ref(model.raw_ref),
        normalizedText=model.normalized_text,
        approxTokens=model.approx_tokens,
        relatedHints=list(model.related_hints or []),
        createdAt=model.created_at,
    )


def _tree_plan_record(model: TreePlanORM) -> TreePlanRecord:
    return TreePlanRecord(
        id=model.id,
        importJobId=model.import_job_id,
        status=model.status,
        candidateNodePayloads=list(model.candidate_node_payloads or []),
        candidateEdgePayloads=list(model.candidate_edge_payloads or []),
        candidateSourceAnnotations=list(model.candidate_source_annotations or []),
        discardedFragmentRefs=list(model.discarded_fragment_refs or []),
        rationale=model.rationale,
        proposedBy=_actor(model.proposed_by),
        createdAt=model.created_at,
    )


def _task_record(model: TaskORM) -> TaskRecord:
    return TaskRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        branchId=model.branch_id,
        title=model.title,
        goal=model.goal,
        status=model.status,
        currentFocus=model.current_focus,
        currentObjective=model.current_objective,
        resumeMessage=model.resume_message,
        restartMessage=model.restart_message,
        ownerProfileId=model.owner_profile_id,
        executionRootNodeId=model.execution_root_node_id,
        activeSnapshotId=model.active_snapshot_id,
        budget=BudgetState.model_validate(model.budget or {}),
        pauseRequested=model.pause_requested,
        lastSafeStopAt=model.last_safe_stop_at,
        startedAt=model.started_at,
        endedAt=model.ended_at,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


def _agent_run_record(model: AgentRunORM) -> AgentRunRecord:
    return AgentRunRecord(
        id=model.id,
        taskId=model.task_id,
        projectId=model.project_id,
        branchId=model.branch_id,
        parentRunId=model.parent_run_id,
        runType=model.run_type,
        selectedModel=model.selected_model,
        selectedProvider=model.selected_provider,
        routeDecisionId=model.route_decision_id,
        status=model.status,
        nextObjective=model.next_objective,
        inputTokensUsed=model.input_tokens_used,
        outputTokensUsed=model.output_tokens_used,
        costUsed=model.cost_used,
        startedAt=model.started_at,
        endedAt=model.ended_at,
    )


def _task_snapshot_record(model: TaskSnapshotORM) -> TaskSnapshotSummary:
    return TaskSnapshotSummary(
        id=model.id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        projectId=model.project_id,
        branchId=model.branch_id,
        snapshotType=model.snapshot_type,
        status=model.status,
        resumeToken=model.resume_token,
        contextRef=_external_ref(model.context_ref),
        rootMountRef=_external_ref(model.root_mount_ref),
        pendingWrites=_entity_refs(model.pending_writes or []),
        pendingActions=list(model.pending_actions or []),
        resumeMessage=model.resume_message,
        safeStopReason=model.safe_stop_reason,
        createdAt=model.created_at,
        consumedAt=model.consumed_at,
        safeToPause=model.safe_to_pause,
        blockers=list(model.blockers or []),
    )


def _route_decision_record(model: ModelRouteDecisionORM) -> ModelRouteDecision:
    return ModelRouteDecision(
        id=model.id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        selectedModel=model.selected_model,
        selectedProvider=model.selected_provider,
        candidateModels=list(model.candidate_models or []),
        reason=model.reason,
        budgetScore=model.budget_score,
        qualityScore=model.quality_score,
        latencyScore=model.latency_score,
        routePolicyVersion=model.route_policy_version,
        createdAt=model.created_at,
    )


def _module_install_record(model: ModuleInstallORM) -> ModuleInstallRecord:
    return ModuleInstallRecord(
        id=model.id,
        moduleId=model.module_id,
        moduleVersion=model.module_version,
        desiredState=model.desired_state,
        lifecycleState=model.lifecycle_state,
        runtimeMode=model.runtime_mode,
        manifestRef=_external_ref(model.manifest_ref),
        configBindingId=model.config_binding_id,
        installedAt=model.installed_at,
        enabledAt=model.enabled_at,
        disabledAt=model.disabled_at,
        lastError=model.last_error,
    )


def _module_config_binding_record(model: ModuleConfigBindingORM) -> ModuleConfigBinding:
    return ModuleConfigBinding(
        id=model.id,
        moduleInstallId=model.module_install_id,
        configSchemaVersion=model.config_schema_version,
        effectiveConfigRef=_external_ref(model.effective_config_ref),
        sourceMode=model.source_mode,
        updatedAt=model.updated_at,
        updatedBy=_actor(model.updated_by),
    )


def _hook_record(model: HookContributionORM) -> HookContributionRecord:
    return HookContributionRecord(
        id=model.id,
        moduleInstallId=model.module_install_id,
        hookName=model.hook_name,
        implementationRef=model.implementation_ref,
        executionOrder=model.execution_order,
        timeoutMs=model.timeout_ms,
        sideEffects=model.side_effects,
        enabled=model.enabled,
        createdAt=model.created_at,
    )


def _subscription_record(model: EventSubscriptionORM) -> EventSubscriptionRecord:
    return EventSubscriptionRecord(
        id=model.id,
        moduleInstallId=model.module_install_id,
        eventType=model.event_type,
        consumerGroup=model.consumer_group,
        deliveryMode=model.delivery_mode,
        status=model.status,
        createdAt=model.created_at,
        updatedAt=model.updated_at,
    )


def _health_record(model: HealthReportORM) -> HealthReport:
    return HealthReport(
        id=model.id,
        moduleInstallId=model.module_install_id,
        status=model.status,
        summary=model.summary,
        detailsRef=_external_ref(model.details_ref),
        observedAt=model.observed_at,
    )


def _outbox_record(model: OutboxRecordORM) -> OutboxRecord:
    return OutboxRecord(
        id=model.id,
        projectId=model.project_id,
        aggregateType=model.aggregate_type,
        aggregateId=model.aggregate_id,
        eventType=model.event_type,
        eventVersion=model.event_version,
        payloadRef=_external_ref(model.payload_ref),
        publishStatus=model.publish_status,
        attempts=model.attempts,
        availableAt=model.available_at,
        publishedAt=model.published_at,
        lastError=model.last_error,
        createdAt=model.created_at,
    )


def _ensure_branch_roots(
    session: Session,
    *,
    project_id: str,
    space_id: str,
    branch_id: str,
    created_by: dict[str, Any] | ActorRef | None,
    now: datetime | None = None,
) -> dict[str, str]:
    timestamp = now or utc_now()
    actor = _actor(created_by)
    actor_payload = actor.model_dump(mode="json")
    root_ids: dict[str, str] = {}

    for root_branch, title in ROOT_BRANCH_TITLES.items():
        node_id = new_id("node", project_id, branch_id, root_branch, stable=True)
        version_id = new_id("ver", node_id, 1, stable=True)
        root_ids[root_branch] = node_id
        node = session.get(NodeORM, node_id)
        if node is None:
            node = NodeORM(
                id=node_id,
                project_id=project_id,
                space_id=space_id,
                branch_id=branch_id,
                parent_id=None,
                root_branch=root_branch,
                node_type="root",
                status="active",
                title=title,
                content=ROOT_BRANCH_CONTENTS[root_branch],
                detail_level=0,
                importance=1.0,
                stability=1.0,
                forget_rate=0.0,
                feedforward_score=1.0,
                access_score=1.0,
                activity_k=0.0,
                float_score=0.0,
                latest_version_id=version_id,
                merged_into_node_id=None,
                children_count=0,
                edge_count=0,
                tree_path=root_branch,
                created_at=timestamp,
                created_by=actor_payload,
                updated_at=timestamp,
                updated_by=actor_payload,
            )
            session.add(node)
        elif not node.latest_version_id:
            node.latest_version_id = version_id
            node.updated_at = timestamp
            node.updated_by = actor_payload

        version = session.get(NodeVersionORM, version_id)
        if version is None:
            version = NodeVersionORM(
                id=version_id,
                node_id=node_id,
                version_no=1,
                title_snapshot=title,
                content_snapshot=ROOT_BRANCH_CONTENTS[root_branch],
                parent_id_snapshot=None,
                score_snapshot={
                    "importance": 1.0,
                    "stability": 1.0,
                    "forgetRate": 0.0,
                    "feedforwardScore": 1.0,
                    "accessScore": 1.0,
                    "activityK": 0.0,
                    "floatScore": 0.0,
                },
                change_reason="bootstrap-root-node",
                derived_from_version_id=None,
                created_at=timestamp,
                created_by=actor_payload,
            )
            session.add(version)

    session.flush()
    return {
        "projectId": project_id,
        "spaceId": space_id,
        "branchId": branch_id,
        "identityRootNodeId": root_ids["identity"],
        "contextRootNodeId": root_ids["context"],
        "executionRootNodeId": root_ids["execution"],
    }


def _pull_request_record(model: PullRequestORM) -> PullRequestRecord:
    return PullRequestRecord(
        id=model.id,
        projectId=model.project_id,
        sourceBranchId=model.source_branch_id,
        targetBranchId=model.target_branch_id,
        title=model.title,
        summary=model.summary,
        status=model.status,
        createdBy=_actor(model.created_by),
        reviewedBy=_actor(model.reviewed_by) if model.reviewed_by else None,
        externalId=model.external_id,
        externalUrl=model.external_url,
        mergeCommitRef=model.merge_commit_ref,
        mergedAt=model.merged_at,
        createdAt=model.created_at,
    )


def _review_comment_record(model: ReviewCommentORM) -> ReviewCommentRecord:
    return ReviewCommentRecord(
        id=model.id,
        prId=model.pr_id,
        author=_actor(model.author),
        targetKind=model.target_kind,
        targetId=model.target_id,
        body=model.body,
        status=model.status,
        createdAt=model.created_at,
        resolvedAt=model.resolved_at,
    )


class WorkspaceBootstrapRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_workspace(self) -> dict[str, str]:
        now = utc_now()
        system_actor = _actor(None)

        project = self.session.get(ProjectORM, DEFAULT_PROJECT_ID)
        if project is None:
            project = ProjectORM(
                id=DEFAULT_PROJECT_ID,
                display_name="Project Yggdrasil",
                status="active",
                export_policy="project-package-only",
                created_at=now,
                created_by=system_actor.model_dump(mode="json"),
            )
            self.session.add(project)

        space = self.session.get(SpaceORM, DEFAULT_SPACE_ID)
        if space is None:
            space = SpaceORM(
                id=DEFAULT_SPACE_ID,
                project_id=DEFAULT_PROJECT_ID,
                space_type="default",
                status="active",
                owner_subject=None,
                created_at=now,
            )
            self.session.add(space)

        branch = self.session.get(MemoryBranchORM, DEFAULT_BRANCH_ID)
        if branch is None:
            branch = MemoryBranchORM(
                id=DEFAULT_BRANCH_ID,
                project_id=DEFAULT_PROJECT_ID,
                space_id=DEFAULT_SPACE_ID,
                name="main",
                base_branch_id=None,
                head_ref=None,
                status="active",
                created_at=now,
                created_by=system_actor.model_dump(mode="json"),
            )
            self.session.add(branch)

        self.session.flush()
        return _ensure_branch_roots(
            self.session,
            project_id=DEFAULT_PROJECT_ID,
            space_id=DEFAULT_SPACE_ID,
            branch_id=DEFAULT_BRANCH_ID,
            created_by=system_actor,
            now=now,
        )

    def ensure_branch_workspace(
        self,
        *,
        branch_id: str,
        project_id: str = DEFAULT_PROJECT_ID,
        space_id: str = DEFAULT_SPACE_ID,
        branch_name: str | None = None,
        base_branch_id: str | None = None,
        created_by: dict[str, Any] | ActorRef | None = None,
    ) -> dict[str, str]:
        now = utc_now()
        actor = _actor(created_by)

        if project_id == DEFAULT_PROJECT_ID and space_id == DEFAULT_SPACE_ID:
            self.ensure_default_workspace()

        project = self.session.get(ProjectORM, project_id)
        if project is None:
            raise KeyError(f"Project {project_id} not found.")
        space = self.session.get(SpaceORM, space_id)
        if space is None:
            raise KeyError(f"Space {space_id} not found.")

        branch = self.session.get(MemoryBranchORM, branch_id)
        if branch is None:
            branch = MemoryBranchORM(
                id=branch_id,
                project_id=project_id,
                space_id=space_id,
                name=branch_name or branch_id,
                base_branch_id=base_branch_id,
                head_ref=None,
                status="active",
                created_at=now,
                created_by=actor.model_dump(mode="json"),
            )
            self.session.add(branch)
        else:
            if branch_name is not None:
                branch.name = branch_name
            if base_branch_id is not None:
                branch.base_branch_id = base_branch_id
            if branch.status == "deleted":
                branch.status = "active"

        self.session.flush()
        return _ensure_branch_roots(
            self.session,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            created_by=actor,
            now=now,
        )


class NodeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_nodes(self, *, branch_id: str | None = None, limit: int = 100) -> list[NodeRecord]:
        statement = sa.select(NodeORM).order_by(NodeORM.created_at.asc()).limit(limit)
        if branch_id:
            statement = statement.where(NodeORM.branch_id == branch_id)
        return [_node_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_node(self, node_id: str) -> NodeRecord | None:
        model = self.session.get(NodeORM, node_id)
        return _node_record(model) if model else None

    def get_edge(self, edge_id: str) -> EdgeRecord | None:
        model = self.session.get(EdgeORM, edge_id)
        return _edge_record(model) if model else None

    def get_source_annotation(self, annotation_id: str) -> SourceAnnotationRecord | None:
        model = self.session.get(SourceAnnotationORM, annotation_id)
        return _source_annotation_record(model) if model else None

    def list_versions(self, node_id: str, limit: int = 100) -> list[NodeVersionRecord]:
        statement = (
            sa.select(NodeVersionORM)
            .where(NodeVersionORM.node_id == node_id)
            .order_by(NodeVersionORM.version_no.asc())
            .limit(limit)
        )
        return [_node_version_record(model) for model in self.session.execute(statement).scalars().all()]

    def list_edges(self, *, branch_id: str | None = None, node_id: str | None = None, limit: int = 200) -> list[EdgeRecord]:
        statement = sa.select(EdgeORM).order_by(EdgeORM.created_at.asc()).limit(limit)
        if branch_id:
            statement = statement.where(EdgeORM.branch_id == branch_id)
        if node_id:
            statement = statement.where(sa.or_(EdgeORM.from_node_id == node_id, EdgeORM.to_node_id == node_id))
        return [_edge_record(model) for model in self.session.execute(statement).scalars().all()]

    def list_source_annotations(
        self,
        *,
        owner_kind: str | None = None,
        owner_id: str | None = None,
        branch_id: str | None = None,
        limit: int = 200,
    ) -> list[SourceAnnotationRecord]:
        statement = sa.select(SourceAnnotationORM).order_by(SourceAnnotationORM.created_at.asc()).limit(limit)
        if owner_kind:
            statement = statement.where(SourceAnnotationORM.owner_kind == owner_kind)
        if owner_id:
            statement = statement.where(SourceAnnotationORM.owner_id == owner_id)
        if branch_id:
            statement = statement.where(SourceAnnotationORM.branch_id == branch_id)
        return [_source_annotation_record(model) for model in self.session.execute(statement).scalars().all()]

    def root_mount_refs(self, project_id: str, branch_id: str, execution_root_node_id: str | None = None) -> tuple[list[EntityRef], list[EntityRef], list[EntityRef]]:
        identity_id = new_id("node", project_id, branch_id, "identity", stable=True)
        context_id = new_id("node", project_id, branch_id, "context", stable=True)
        execution_id = execution_root_node_id or new_id("node", project_id, branch_id, "execution", stable=True)
        return (
            [EntityRef(kind="node", id=identity_id)],
            [EntityRef(kind="node", id=context_id)],
            [EntityRef(kind="node", id=execution_id)],
        )

    def create_node(self, payload: dict[str, Any]) -> NodeRecord:
        now = utc_now()
        actor = _actor(payload.get("createdBy") or payload.get("updatedBy"), default_type="user", default_id="core-api")
        node_id = str(payload.get("id") or new_id("node", payload.get("branchId") or DEFAULT_BRANCH_ID, payload.get("title") or now.isoformat()))
        version_id = str(payload.get("latestVersionId") or new_id("ver", node_id, 1, stable=True))
        parent_id = payload.get("parentId")
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        space_id = str(payload.get("spaceId") or DEFAULT_SPACE_ID)
        branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)
        tree_path = str(payload.get("treePath")) if payload.get("treePath") is not None else None
        if tree_path is None and parent_id is not None:
            parent = self.session.get(NodeORM, str(parent_id))
            if parent is not None and parent.tree_path:
                tree_path = f"{parent.tree_path}.{node_id}"
            elif parent is not None:
                tree_path = f"{parent.id}.{node_id}"
        node = NodeORM(
            id=node_id,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            parent_id=str(parent_id) if parent_id is not None else None,
            root_branch=str(payload.get("rootBranch") or "none"),
            node_type=str(payload.get("nodeType") or "detail"),
            status=str(payload.get("status") or "active"),
            title=str(payload.get("title") or "Untitled Node"),
            content=str(payload.get("content") or ""),
            detail_level=int(payload.get("detailLevel") or 1),
            importance=float(payload.get("importance", 0.5)),
            stability=float(payload.get("stability", 0.5)),
            forget_rate=float(payload.get("forgetRate", 0.2)),
            feedforward_score=float(payload.get("feedforwardScore", 0.5)),
            access_score=float(payload.get("accessScore", 0.0)),
            activity_k=float(payload.get("activityK", 0.4)),
            float_score=float(payload.get("floatScore", 0.3)),
            latest_version_id=version_id,
            merged_into_node_id=str(payload.get("mergedIntoNodeId")) if payload.get("mergedIntoNodeId") is not None else None,
            children_count=0,
            edge_count=0,
            tree_path=tree_path,
            created_at=now,
            created_by=actor.model_dump(mode="json"),
            updated_at=now,
            updated_by=actor.model_dump(mode="json"),
        )
        self.session.add(node)
        version = NodeVersionORM(
            id=version_id,
            node_id=node_id,
            version_no=1,
            title_snapshot=node.title,
            content_snapshot=node.content,
            parent_id_snapshot=node.parent_id,
            score_snapshot=_score_snapshot_from_node(node),
            change_reason=str(payload.get("changeReason") or "initial-create"),
            derived_from_version_id=None,
            created_at=now,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(version)
        if node.parent_id:
            parent = self.session.get(NodeORM, node.parent_id)
            if parent is not None:
                parent.children_count += 1
                parent.updated_at = now
                parent.updated_by = actor.model_dump(mode="json")
        self.session.flush()
        return _node_record(node)

    def create_edge(self, payload: dict[str, Any]) -> EdgeRecord:
        now = utc_now()
        actor = _actor(payload.get("createdBy") or payload.get("updatedBy"), default_type="user", default_id="core-api")
        from_node_id = str(payload.get("fromNodeId"))
        to_node_id = str(payload.get("toNodeId"))
        from_node = self.session.get(NodeORM, from_node_id)
        to_node = self.session.get(NodeORM, to_node_id)
        if from_node is None or to_node is None:
            raise KeyError("Both fromNodeId and toNodeId must reference existing nodes.")
        edge = EdgeORM(
            id=str(payload.get("id") or new_id("edge", from_node_id, to_node_id, payload.get("relationType") or "related")),
            project_id=str(payload.get("projectId") or from_node.project_id),
            space_id=str(payload.get("spaceId") or from_node.space_id),
            branch_id=str(payload.get("branchId") or from_node.branch_id),
            from_node_id=from_node_id,
            to_node_id=to_node_id,
            relation_type=str(payload.get("relationType") or "related-to"),
            weight=float(payload.get("weight", 0.5)),
            reason=str(payload.get("reason") or "Derived during import materialization."),
            evidence_annotation_ids=list(payload.get("evidenceAnnotationIds") or []),
            status=str(payload.get("status") or "active"),
            created_at=now,
            created_by=actor.model_dump(mode="json"),
            updated_at=now,
            updated_by=actor.model_dump(mode="json"),
        )
        self.session.add(edge)
        from_node.edge_count += 1
        from_node.updated_at = now
        from_node.updated_by = actor.model_dump(mode="json")
        if to_node.id != from_node.id:
            to_node.edge_count += 1
            to_node.updated_at = now
            to_node.updated_by = actor.model_dump(mode="json")
        self.session.flush()
        return _edge_record(edge)

    def append_version(self, node_id: str, payload: dict[str, Any]) -> NodeVersionRecord:
        node = self.session.get(NodeORM, node_id)
        if node is None:
            raise KeyError(f"Node {node_id} not found.")

        actor = _actor(payload.get("createdBy") or payload.get("updatedBy"), default_type="user", default_id="core-api")
        next_version = int(
            self.session.execute(
                sa.select(sa.func.coalesce(sa.func.max(NodeVersionORM.version_no), 0)).where(NodeVersionORM.node_id == node_id)
            ).scalar_one()
        ) + 1
        if "title" in payload:
            node.title = str(payload["title"])
        if "content" in payload:
            node.content = str(payload["content"])
        if "parentId" in payload:
            node.parent_id = str(payload["parentId"]) if payload["parentId"] is not None else None
        for field_name, attribute in (
            ("importance", "importance"),
            ("stability", "stability"),
            ("forgetRate", "forget_rate"),
            ("feedforwardScore", "feedforward_score"),
            ("accessScore", "access_score"),
            ("activityK", "activity_k"),
            ("floatScore", "float_score"),
        ):
            if field_name in payload:
                setattr(node, attribute, float(payload[field_name]))
        node.updated_at = utc_now()
        node.updated_by = actor.model_dump(mode="json")
        version_id = str(payload.get("id") or new_id("ver", node_id, next_version, stable=True))
        version = NodeVersionORM(
            id=version_id,
            node_id=node_id,
            version_no=next_version,
            title_snapshot=node.title,
            content_snapshot=node.content,
            parent_id_snapshot=node.parent_id,
            score_snapshot=_score_snapshot_from_node(node),
            change_reason=str(payload.get("changeReason") or f"update-v{next_version}"),
            derived_from_version_id=node.latest_version_id,
            created_at=node.updated_at,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(version)
        node.latest_version_id = version_id
        self.session.flush()
        return _node_version_record(version)

    def add_source_annotation(self, owner_kind: str, owner_id: str, payload: dict[str, Any]) -> SourceAnnotationRecord:
        actor = _actor(payload.get("createdBy"), default_type="user", default_id="core-api")
        annotation = SourceAnnotationORM(
            id=str(payload.get("id") or new_id("srcann", owner_kind, owner_id, utc_now().isoformat())),
            project_id=str(payload.get("projectId") or DEFAULT_PROJECT_ID),
            branch_id=str(payload.get("branchId") or DEFAULT_BRANCH_ID),
            owner_kind=owner_kind,
            owner_id=owner_id,
            source_type=str(payload.get("sourceType") or "system"),
            source_ref=_external_ref(payload.get("sourceRef")).model_dump(mode="json") if payload.get("sourceRef") else None,
            excerpt=str(payload.get("excerpt")) if payload.get("excerpt") is not None else None,
            inference_summary=str(payload.get("inferenceSummary")) if payload.get("inferenceSummary") is not None else None,
            evidence_refs=[reference.model_dump(mode="json") for reference in _entity_refs(payload.get("evidenceRefs") or [])],
            confidence=float(payload.get("confidence", 1.0)),
            created_at=utc_now(),
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(annotation)
        self.session.flush()
        return _source_annotation_record(annotation)


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_tasks(self, *, status: str | None = None, limit: int = 100) -> list[TaskRecord]:
        statement = sa.select(TaskORM).order_by(TaskORM.created_at.desc()).limit(limit)
        if status:
            statement = statement.where(TaskORM.status == status)
        return [_task_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_task(self, task_id: str) -> TaskRecord | None:
        model = self.session.get(TaskORM, task_id)
        return _task_record(model) if model else None

    def update_task(self, task_id: str, payload: dict[str, Any]) -> TaskRecord:
        task = self.session.get(TaskORM, task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")

        now = payload.get("updatedAt") or utc_now()

        if "status" in payload:
            task.status = str(payload["status"])
            if task.status in {"running", "pause-requested", "restarting"}:
                task.started_at = payload.get("startedAt") or task.started_at or now
            if task.status in {"completed", "failed", "cancelled"}:
                task.ended_at = payload.get("endedAt") or now

        if "currentFocus" in payload:
            task.current_focus = str(payload["currentFocus"]) if payload["currentFocus"] is not None else None
        if "currentObjective" in payload:
            task.current_objective = (
                str(payload["currentObjective"]) if payload["currentObjective"] is not None else None
            )
        if "resumeMessage" in payload:
            task.resume_message = str(payload["resumeMessage"]) if payload["resumeMessage"] is not None else None
        if "restartMessage" in payload:
            task.restart_message = str(payload["restartMessage"]) if payload["restartMessage"] is not None else None
        if "executionRootNodeId" in payload:
            task.execution_root_node_id = (
                str(payload["executionRootNodeId"]) if payload["executionRootNodeId"] is not None else None
            )
        if "activeSnapshotId" in payload:
            task.active_snapshot_id = str(payload["activeSnapshotId"]) if payload["activeSnapshotId"] is not None else None
        if "pauseRequested" in payload:
            task.pause_requested = bool(payload["pauseRequested"])
        if "lastSafeStopAt" in payload:
            task.last_safe_stop_at = payload["lastSafeStopAt"]
        if "budget" in payload or "budgetState" in payload:
            budget = BudgetState.model_validate(payload.get("budget") or payload.get("budgetState") or {})
            task.budget = budget.model_dump(by_alias=True, mode="json")

        task.updated_at = now
        self.session.flush()
        return _task_record(task)

    def get_agent_run(self, agent_run_id: str) -> AgentRunRecord | None:
        model = self.session.get(AgentRunORM, agent_run_id)
        return _agent_run_record(model) if model else None

    def list_agent_runs(self, task_id: str, *, limit: int = 100) -> list[AgentRunRecord]:
        statement = (
            sa.select(AgentRunORM)
            .where(AgentRunORM.task_id == task_id)
            .order_by(AgentRunORM.started_at.desc())
            .limit(limit)
        )
        return [_agent_run_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_latest_agent_run(self, task_id: str, *, statuses: set[str] | None = None) -> AgentRunRecord | None:
        statement = (
            sa.select(AgentRunORM)
            .where(AgentRunORM.task_id == task_id)
            .order_by(AgentRunORM.started_at.desc())
            .limit(20)
        )
        models = self.session.execute(statement).scalars().all()
        for model in models:
            if statuses is None or model.status in statuses:
                return _agent_run_record(model)
        return None

    def update_agent_run(self, agent_run_id: str, payload: dict[str, Any]) -> AgentRunRecord:
        run = self.session.get(AgentRunORM, agent_run_id)
        if run is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")

        if "parentRunId" in payload:
            run.parent_run_id = str(payload["parentRunId"]) if payload["parentRunId"] is not None else None
        if "selectedModel" in payload:
            run.selected_model = str(payload["selectedModel"])
        if "selectedProvider" in payload:
            run.selected_provider = str(payload["selectedProvider"]) if payload["selectedProvider"] is not None else None
        if "routeDecisionId" in payload:
            run.route_decision_id = str(payload["routeDecisionId"]) if payload["routeDecisionId"] is not None else None
        if "status" in payload:
            run.status = str(payload["status"])
            if run.status in {"completed", "failed", "aborted"}:
                run.ended_at = payload.get("endedAt") or utc_now()
        if "nextObjective" in payload:
            run.next_objective = str(payload["nextObjective"]) if payload["nextObjective"] is not None else None
        if "inputTokensUsed" in payload:
            run.input_tokens_used = int(payload["inputTokensUsed"])
        if "outputTokensUsed" in payload:
            run.output_tokens_used = int(payload["outputTokensUsed"])
        if "costUsed" in payload:
            run.cost_used = float(payload["costUsed"])

        self.session.flush()
        return _agent_run_record(run)

    def create_task(self, payload: dict[str, Any]) -> TaskRecord:
        now = utc_now()
        budget = BudgetState.model_validate(payload.get("budget") or payload.get("budgetState") or {})
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)
        task = TaskORM(
            id=str(payload.get("id") or new_id("task", payload.get("title") or now.isoformat())),
            project_id=project_id,
            space_id=str(payload.get("spaceId") or DEFAULT_SPACE_ID),
            branch_id=branch_id,
            title=str(payload.get("title") or "Untitled Task"),
            goal=str(payload.get("goal") or payload.get("objective") or ""),
            status=str(payload.get("status") or "draft"),
            current_focus=str(payload.get("currentFocus")) if payload.get("currentFocus") is not None else None,
            current_objective=str(payload.get("currentObjective")) if payload.get("currentObjective") is not None else None,
            resume_message=str(payload.get("resumeMessage")) if payload.get("resumeMessage") is not None else None,
            restart_message=str(payload.get("restartMessage")) if payload.get("restartMessage") is not None else None,
            owner_profile_id=str(payload.get("ownerProfileId") or DEFAULT_OWNER_PROFILE_ID),
            execution_root_node_id=str(payload.get("executionRootNodeId") or new_id("node", project_id, branch_id, "execution", stable=True)),
            active_snapshot_id=None,
            budget=budget.model_dump(by_alias=True, mode="json"),
            pause_requested=bool(payload.get("pauseRequested", False)),
            last_safe_stop_at=None,
            started_at=None,
            ended_at=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(task)
        self.session.flush()
        return _task_record(task)

    def create_agent_run(self, task_id: str, payload: dict[str, Any]) -> AgentRunRecord:
        task = self.session.get(TaskORM, task_id)
        if task is None:
            raise KeyError(f"Task {task_id} not found.")
        now = utc_now()
        run = AgentRunORM(
            id=str(payload.get("id") or new_id("run", task_id, now.isoformat())),
            task_id=task_id,
            project_id=task.project_id,
            branch_id=task.branch_id,
            parent_run_id=str(payload.get("parentRunId")) if payload.get("parentRunId") is not None else None,
            run_type=str(payload.get("runType") or "main"),
            selected_model=str(payload.get("selectedModel") or "gpt-5.4"),
            selected_provider=str(payload.get("selectedProvider")) if payload.get("selectedProvider") is not None else None,
            route_decision_id=str(payload.get("routeDecisionId")) if payload.get("routeDecisionId") is not None else None,
            status=str(payload.get("status") or "initializing"),
            next_objective=str(payload.get("nextObjective")) if payload.get("nextObjective") is not None else None,
            input_tokens_used=int(payload.get("inputTokensUsed", 0)),
            output_tokens_used=int(payload.get("outputTokensUsed", 0)),
            cost_used=float(payload.get("costUsed", 0.0)),
            started_at=now,
            ended_at=None,
        )
        self.session.add(run)
        if task.status in {"draft", "queued"} and run.status in {"initializing", "mounting", "running"}:
            task.status = "running"
            task.started_at = task.started_at or now
            task.updated_at = now
        self.session.flush()
        return _agent_run_record(run)

    def create_snapshot(self, summary: TaskSnapshotSummary) -> TaskSnapshotSummary:
        task = self.session.get(TaskORM, summary.task_id)
        if task is None:
            raise KeyError(f"Task {summary.task_id} not found.")
        snapshot = TaskSnapshotORM(
            id=summary.id,
            task_id=summary.task_id,
            agent_run_id=summary.agent_run_id,
            project_id=summary.project_id,
            branch_id=summary.branch_id,
            snapshot_type=summary.snapshot_type,
            status=summary.status,
            resume_token=summary.resume_token,
            context_ref=summary.context_ref.model_dump(mode="json"),
            root_mount_ref=summary.root_mount_ref.model_dump(mode="json"),
            pending_writes=[reference.model_dump(mode="json") for reference in summary.pending_writes],
            pending_actions=list(summary.pending_actions),
            resume_message=summary.resume_message,
            safe_stop_reason=summary.safe_stop_reason,
            created_at=summary.created_at,
            consumed_at=None,
            safe_to_pause=summary.safe_to_pause,
            blockers=list(summary.blockers),
        )
        self.session.add(snapshot)
        task.active_snapshot_id = summary.id
        if summary.safe_to_pause:
            task.last_safe_stop_at = summary.created_at
        task.updated_at = summary.created_at
        self.session.flush()
        return _task_snapshot_record(snapshot)

    def get_snapshot(self, snapshot_id: str) -> TaskSnapshotSummary | None:
        model = self.session.get(TaskSnapshotORM, snapshot_id)
        return _task_snapshot_record(model) if model else None

    def get_snapshot_by_resume_token(self, resume_token: str) -> TaskSnapshotSummary | None:
        statement = sa.select(TaskSnapshotORM).where(TaskSnapshotORM.resume_token == resume_token)
        model = self.session.execute(statement).scalar_one_or_none()
        return _task_snapshot_record(model) if model else None

    def update_snapshot(
        self,
        snapshot_id: str,
        *,
        status: str | None = None,
        consumed_at: datetime | None = None,
        blockers: list[str] | None = None,
    ) -> TaskSnapshotSummary:
        snapshot = self.session.get(TaskSnapshotORM, snapshot_id)
        if snapshot is None:
            raise KeyError(f"Snapshot {snapshot_id} not found.")
        if status is not None:
            snapshot.status = status
        if consumed_at is not None:
            snapshot.consumed_at = consumed_at
        if blockers is not None:
            snapshot.blockers = list(blockers)
        self.session.flush()
        return _task_snapshot_record(snapshot)

    def supersede_snapshots(self, task_id: str, *, keep_snapshot_id: str | None = None) -> int:
        statement = sa.select(TaskSnapshotORM).where(
            TaskSnapshotORM.task_id == task_id,
            TaskSnapshotORM.status.in_(["created", "flushed", "restorable"]),
        )
        updated = 0
        for snapshot in self.session.execute(statement).scalars().all():
            if keep_snapshot_id is not None and snapshot.id == keep_snapshot_id:
                continue
            snapshot.status = "superseded"
            updated += 1
        self.session.flush()
        return updated

    def list_snapshots(self, task_id: str) -> list[TaskSnapshotSummary]:
        statement = sa.select(TaskSnapshotORM).where(TaskSnapshotORM.task_id == task_id).order_by(TaskSnapshotORM.created_at.desc())
        return [_task_snapshot_record(model) for model in self.session.execute(statement).scalars().all()]


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_import_jobs(self, *, status: str | None = None, limit: int = 100) -> list[ImportJobRecord]:
        statement = sa.select(ImportJobORM).order_by(ImportJobORM.created_at.desc()).limit(limit)
        if status:
            statement = statement.where(ImportJobORM.status == status)
        return [_import_job_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_import_job(self, import_job_id: str) -> ImportJobRecord | None:
        model = self.session.get(ImportJobORM, import_job_id)
        return _import_job_record(model) if model else None

    def create_import_job(self, payload: dict[str, Any]) -> ImportJobRecord:
        now = utc_now()
        policy = _import_policy(payload.get("importPolicy"))
        requested_by = _actor(payload.get("requestedBy"), default_type="user", default_id="core-api")
        model = ImportJobORM(
            id=str(payload.get("id") or new_id("import", payload.get("sourceKind") or "stream", now.isoformat())),
            project_id=str(payload.get("projectId") or DEFAULT_PROJECT_ID),
            branch_id=str(payload.get("branchId") or DEFAULT_BRANCH_ID),
            source_kind=str(payload.get("sourceKind") or "stream"),
            status=str(payload.get("status") or "accepted"),
            import_policy=policy.model_dump(by_alias=True, mode="json"),
            requested_by=requested_by.model_dump(mode="json"),
            token_budget=int(payload["tokenBudget"]) if payload.get("tokenBudget") is not None else None,
            cost_budget=float(payload["costBudget"]) if payload.get("costBudget") is not None else None,
            failure_reason=str(payload.get("failureReason")) if payload.get("failureReason") is not None else None,
            started_at=None,
            finished_at=None,
            created_at=now,
        )
        self.session.add(model)
        self.session.flush()
        return _import_job_record(model)

    def set_import_job_status(
        self,
        import_job_id: str,
        status: str,
        *,
        failure_reason: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> ImportJobRecord:
        model = self.session.get(ImportJobORM, import_job_id)
        if model is None:
            raise KeyError(f"Import job {import_job_id} not found.")
        now = utc_now()
        model.status = status
        if model.started_at is None and status in {"preprocessing", "pre-reading", "planning", "materializing", "completed", "failed"}:
            model.started_at = started_at or now
        if status in {"completed", "failed", "cancelled"}:
            model.finished_at = finished_at or now
        if failure_reason is not None:
            model.failure_reason = failure_reason
        self.session.flush()
        return _import_job_record(model)

    def replace_import_fragments(self, import_job_id: str, fragments: list[dict[str, Any]]) -> list[ImportFragmentRecord]:
        if self.session.get(ImportJobORM, import_job_id) is None:
            raise KeyError(f"Import job {import_job_id} not found.")
        self.session.execute(sa.delete(ImportFragmentORM).where(ImportFragmentORM.import_job_id == import_job_id))
        created_at = utc_now()
        created: list[ImportFragmentORM] = []
        for index, fragment in enumerate(fragments, start=1):
            raw_ref = _external_ref(fragment.get("rawRef")) or ExternalRef(
                type="package-entry",
                locator=f"core-api/memory/import-jobs/{import_job_id}/fragments/{index}",
            )
            model = ImportFragmentORM(
                id=str(fragment.get("id") or new_id("frag", import_job_id, index, stable=True)),
                import_job_id=import_job_id,
                ordinal=int(fragment.get("ordinal") or index),
                raw_ref=raw_ref.model_dump(mode="json"),
                normalized_text=str(fragment.get("normalizedText") or fragment.get("text") or ""),
                approx_tokens=int(fragment.get("approxTokens") or max(len(str(fragment.get("normalizedText") or fragment.get("text") or "")) // 4, 1)),
                related_hints=[str(hint) for hint in fragment.get("relatedHints") or []],
                created_at=created_at,
            )
            self.session.add(model)
            created.append(model)
        self.session.flush()
        return [_import_fragment_record(model) for model in sorted(created, key=lambda item: item.ordinal)]

    def list_import_fragments(self, import_job_id: str, limit: int = 500) -> list[ImportFragmentRecord]:
        statement = (
            sa.select(ImportFragmentORM)
            .where(ImportFragmentORM.import_job_id == import_job_id)
            .order_by(ImportFragmentORM.ordinal.asc())
            .limit(limit)
        )
        return [_import_fragment_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_tree_plan(self, payload: dict[str, Any]) -> TreePlanRecord:
        import_job_id = str(payload.get("importJobId"))
        if self.session.get(ImportJobORM, import_job_id) is None:
            raise KeyError(f"Import job {import_job_id} not found.")
        plan_id = str(payload.get("id") or new_id("treeplan", import_job_id, stable=True))
        model = self.session.get(TreePlanORM, plan_id)
        if model is None:
            model = TreePlanORM(
                id=plan_id,
                import_job_id=import_job_id,
                status=str(payload.get("status") or "proposed"),
                candidate_node_payloads=list(payload.get("candidateNodePayloads") or []),
                candidate_edge_payloads=list(payload.get("candidateEdgePayloads") or []),
                candidate_source_annotations=list(payload.get("candidateSourceAnnotations") or []),
                discarded_fragment_refs=list(payload.get("discardedFragmentRefs") or []),
                rationale=str(payload.get("rationale") or "Generated tree plan."),
                proposed_by=_actor(payload.get("proposedBy"), default_type="module", default_id="text-memory").model_dump(mode="json"),
                created_at=payload.get("createdAt") or utc_now(),
            )
            self.session.add(model)
        else:
            model.status = str(payload.get("status") or model.status)
            model.candidate_node_payloads = list(payload.get("candidateNodePayloads") or model.candidate_node_payloads or [])
            model.candidate_edge_payloads = list(payload.get("candidateEdgePayloads") or model.candidate_edge_payloads or [])
            model.candidate_source_annotations = list(payload.get("candidateSourceAnnotations") or model.candidate_source_annotations or [])
            model.discarded_fragment_refs = list(payload.get("discardedFragmentRefs") or model.discarded_fragment_refs or [])
            model.rationale = str(payload.get("rationale") or model.rationale)
            if payload.get("proposedBy") is not None:
                model.proposed_by = _actor(payload.get("proposedBy")).model_dump(mode="json")
        self.session.flush()
        return _tree_plan_record(model)

    def get_tree_plan(self, plan_id: str) -> TreePlanRecord | None:
        model = self.session.get(TreePlanORM, plan_id)
        return _tree_plan_record(model) if model else None

    def get_latest_tree_plan(self, import_job_id: str) -> TreePlanRecord | None:
        statement = (
            sa.select(TreePlanORM)
            .where(TreePlanORM.import_job_id == import_job_id)
            .order_by(TreePlanORM.created_at.desc())
            .limit(1)
        )
        model = self.session.execute(statement).scalar_one_or_none()
        return _tree_plan_record(model) if model else None

    def list_tree_plans(self, import_job_id: str, limit: int = 20) -> list[TreePlanRecord]:
        statement = (
            sa.select(TreePlanORM)
            .where(TreePlanORM.import_job_id == import_job_id)
            .order_by(TreePlanORM.created_at.desc())
            .limit(limit)
        )
        return [_tree_plan_record(model) for model in self.session.execute(statement).scalars().all()]

    def set_tree_plan_status(self, plan_id: str, status: str) -> TreePlanRecord:
        model = self.session.get(TreePlanORM, plan_id)
        if model is None:
            raise KeyError(f"Tree plan {plan_id} not found.")
        model.status = status
        self.session.flush()
        return _tree_plan_record(model)

    def create_retrieval_request(self, payload: dict[str, Any]) -> RetrievalRequestRecord:
        query_text = str(payload.get("queryText")) if payload.get("queryText") is not None else None
        seed_refs = _entity_refs(payload.get("seedNodeRefs") or [])
        if not query_text and not seed_refs:
            raise ValueError("RetrievalRequest requires queryText or seedNodeRefs.")
        now = utc_now()
        model = RetrievalRequestORM(
            id=str(payload.get("id") or new_id("retr", query_text or now.isoformat())),
            project_id=str(payload.get("projectId") or DEFAULT_PROJECT_ID),
            space_id=str(payload.get("spaceId") or DEFAULT_SPACE_ID),
            branch_id=str(payload.get("branchId") or DEFAULT_BRANCH_ID),
            query_text=query_text,
            seed_node_refs=[reference.model_dump(mode="json") for reference in seed_refs],
            traversal_start=str(payload.get("traversalStart") or "mixed"),
            expansion_mode=str(payload.get("expansionMode") or "parallel"),
            read_depth=int(payload.get("readDepth") or 2),
            lateral_hops=int(payload.get("lateralHops") or 1),
            max_related_nodes=int(payload.get("maxRelatedNodes") or 4),
            max_leaf_nodes=int(payload.get("maxLeafNodes") or 6),
            precision_mode=str(payload.get("precisionMode") or "balanced"),
            include_natural_language_summary=bool(payload.get("includeNaturalLanguageSummary", True)),
            include_child_names=bool(payload.get("includeChildNames", True)),
            include_related_names=bool(payload.get("includeRelatedNames", True)),
            token_budget=int(payload["tokenBudget"]) if payload.get("tokenBudget") is not None else None,
            created_at=now,
        )
        self.session.add(model)
        self.session.flush()
        return _retrieval_request_record(model)


class RuntimeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_model_route_decision(self, payload: dict[str, Any]) -> ModelRouteDecision:
        task_id = str(payload.get("taskId")) if payload.get("taskId") is not None else None
        agent_run_id = str(payload.get("agentRunId")) if payload.get("agentRunId") is not None else None
        if task_id is not None and self.session.get(TaskORM, task_id) is None:
            raise KeyError(f"Task {task_id} not found.")
        if agent_run_id is not None and self.session.get(AgentRunORM, agent_run_id) is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")
        candidate_models: list[dict[str, Any]] = []
        for candidate in payload.get("candidateModels") or []:
            if isinstance(candidate, dict):
                candidate_models.append(candidate)
            else:
                candidate_models.append({"model": str(candidate)})
        record = ModelRouteDecision(
            id=str(payload.get("id") or new_id("route", payload.get("taskId") or payload.get("selectedModel") or utc_now().isoformat())),
            taskId=task_id,
            agentRunId=agent_run_id,
            selectedModel=str(payload.get("selectedModel") or "gpt-5.4"),
            selectedProvider=str(payload.get("selectedProvider")) if payload.get("selectedProvider") is not None else None,
            candidateModels=candidate_models,
            reason=str(payload.get("reason") or "manual-route-decision"),
            budgetScore=float(payload.get("budgetScore", 0.5)),
            qualityScore=float(payload.get("qualityScore", 0.5)),
            latencyScore=float(payload.get("latencyScore", 0.5)),
            routePolicyVersion=str(payload.get("routePolicyVersion") or "v0.1-manual"),
            createdAt=utc_now(),
        )
        model = ModelRouteDecisionORM(
            id=record.id,
            task_id=record.task_id,
            agent_run_id=record.agent_run_id,
            selected_model=record.selected_model,
            selected_provider=record.selected_provider,
            candidate_models=list(record.candidate_models),
            reason=record.reason,
            budget_score=record.budget_score,
            quality_score=record.quality_score,
            latency_score=record.latency_score,
            route_policy_version=record.route_policy_version,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return record

    def list_model_route_decisions(self, *, task_id: str | None = None, limit: int = 100) -> list[ModelRouteDecision]:
        statement = sa.select(ModelRouteDecisionORM).order_by(ModelRouteDecisionORM.created_at.desc()).limit(limit)
        if task_id:
            statement = statement.where(ModelRouteDecisionORM.task_id == task_id)
        return [_route_decision_record(model) for model in self.session.execute(statement).scalars().all()]


class ModuleStateRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_module_installs(self) -> list[ModuleInstallRecord]:
        statement = sa.select(ModuleInstallORM).order_by(ModuleInstallORM.module_id.asc())
        return [_module_install_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_module_install(self, module_id: str) -> ModuleInstallRecord | None:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _module_install_record(model) if model is not None else None

    def upsert_module_install(self, record: ModuleInstallRecord) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == record.module_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = ModuleInstallORM(id=record.id, module_id=record.module_id)
            self.session.add(model)
        model.module_version = record.module_version
        model.desired_state = record.desired_state
        model.lifecycle_state = record.lifecycle_state
        model.runtime_mode = record.runtime_mode
        model.manifest_ref = record.manifest_ref.model_dump(mode="json")
        model.config_binding_id = record.config_binding_id
        model.installed_at = record.installed_at
        model.enabled_at = record.enabled_at
        model.disabled_at = record.disabled_at
        model.last_error = record.last_error
        self.session.flush()
        return _module_install_record(model)

    def set_desired_state(self, module_id: str, desired_state: str) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one()
        model.desired_state = desired_state
        self.session.flush()
        return _module_install_record(model)

    def transition_lifecycle(
        self,
        module_id: str,
        lifecycle_state: str,
        *,
        last_error: str | None = None,
    ) -> ModuleInstallRecord:
        statement = sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id == module_id)
        model = self.session.execute(statement).scalar_one()
        model.lifecycle_state = lifecycle_state
        model.last_error = last_error
        if lifecycle_state == "active":
            model.enabled_at = model.enabled_at or utc_now()
        if lifecycle_state in {"disabled", "removed"}:
            model.disabled_at = utc_now()
        self.session.flush()
        return _module_install_record(model)

    def list_config_bindings(self) -> list[ModuleConfigBinding]:
        statement = sa.select(ModuleConfigBindingORM).order_by(ModuleConfigBindingORM.module_install_id.asc())
        return [_module_config_binding_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_config_binding(
        self,
        *,
        module_install_id: str | None = None,
        binding_id: str | None = None,
    ) -> ModuleConfigBinding | None:
        statement = sa.select(ModuleConfigBindingORM)
        if module_install_id is not None:
            statement = statement.where(ModuleConfigBindingORM.module_install_id == module_install_id)
        if binding_id is not None:
            statement = statement.where(ModuleConfigBindingORM.id == binding_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _module_config_binding_record(model) if model is not None else None

    def upsert_config_binding(self, record: ModuleConfigBinding) -> ModuleConfigBinding:
        statement = sa.select(ModuleConfigBindingORM).where(ModuleConfigBindingORM.module_install_id == record.module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = ModuleConfigBindingORM(id=record.id, module_install_id=record.module_install_id)
            self.session.add(model)
        model.config_schema_version = record.config_schema_version
        model.effective_config_ref = record.effective_config_ref.model_dump(mode="json")
        model.source_mode = record.source_mode
        model.updated_at = record.updated_at
        model.updated_by = record.updated_by.model_dump(mode="json")
        self.session.execute(
            sa.update(ModuleInstallORM)
            .where(ModuleInstallORM.id == record.module_install_id)
            .values(config_binding_id=record.id)
        )
        self.session.flush()
        return _module_config_binding_record(model)

    def list_hooks(self, *, module_install_id: str | None = None) -> list[HookContributionRecord]:
        statement = sa.select(HookContributionORM).order_by(HookContributionORM.execution_order.asc(), HookContributionORM.hook_name.asc())
        if module_install_id is not None:
            statement = statement.where(HookContributionORM.module_install_id == module_install_id)
        return [_hook_record(model) for model in self.session.execute(statement).scalars().all()]

    def replace_hook_contributions(self, module_install_id: str, records: list[HookContributionRecord]) -> list[HookContributionRecord]:
        self.session.execute(sa.delete(HookContributionORM).where(HookContributionORM.module_install_id == module_install_id))
        for record in records:
            self.session.add(
                HookContributionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    hook_name=record.hook_name,
                    implementation_ref=record.implementation_ref,
                    execution_order=record.execution_order,
                    timeout_ms=record.timeout_ms,
                    side_effects=record.side_effects,
                    enabled=record.enabled,
                    created_at=record.created_at,
                )
            )
        self.session.flush()
        return self.list_hooks(module_install_id=module_install_id)

    def list_subscriptions(
        self,
        *,
        module_install_id: str | None = None,
        status: str | None = None,
    ) -> list[EventSubscriptionRecord]:
        statement = sa.select(EventSubscriptionORM).order_by(EventSubscriptionORM.event_type.asc())
        if module_install_id is not None:
            statement = statement.where(EventSubscriptionORM.module_install_id == module_install_id)
        if status is not None:
            statement = statement.where(EventSubscriptionORM.status == status)
        return [_subscription_record(model) for model in self.session.execute(statement).scalars().all()]

    def replace_event_subscriptions(self, module_install_id: str, records: list[EventSubscriptionRecord]) -> list[EventSubscriptionRecord]:
        self.session.execute(sa.delete(EventSubscriptionORM).where(EventSubscriptionORM.module_install_id == module_install_id))
        for record in records:
            self.session.add(
                EventSubscriptionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    event_type=record.event_type,
                    consumer_group=record.consumer_group,
                    delivery_mode=record.delivery_mode,
                    status=record.status,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )
        self.session.flush()
        return self.list_subscriptions(module_install_id=module_install_id)

    def set_runtime_contributions_active(self, module_install_id: str, *, enabled: bool) -> None:
        self.session.execute(
            sa.update(HookContributionORM)
            .where(HookContributionORM.module_install_id == module_install_id)
            .values(enabled=enabled)
        )
        self.session.execute(
            sa.update(EventSubscriptionORM)
            .where(EventSubscriptionORM.module_install_id == module_install_id)
            .values(status="active" if enabled else "paused", updated_at=utc_now())
        )
        self.session.flush()

    def get_health_report(self, module_install_id: str) -> HealthReport | None:
        statement = sa.select(HealthReportORM).where(HealthReportORM.module_install_id == module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        return _health_record(model) if model is not None else None

    def list_health_reports(self) -> list[HealthReport]:
        statement = sa.select(HealthReportORM).order_by(HealthReportORM.module_install_id.asc())
        return [_health_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_health_report(self, record: HealthReport) -> HealthReport:
        statement = sa.select(HealthReportORM).where(HealthReportORM.module_install_id == record.module_install_id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = HealthReportORM(id=record.id, module_install_id=record.module_install_id)
            self.session.add(model)
        model.status = record.status
        model.summary = record.summary
        model.details_ref = record.details_ref.model_dump(mode="json") if record.details_ref else None
        model.observed_at = record.observed_at
        self.session.flush()
        return _health_record(model)

    def sync_snapshot(self, snapshot: ModuleCatalogSnapshot) -> None:
        generated_at = snapshot.generated_at
        current_module_ids = {record.module_id for record in snapshot.installs}
        existing_installs = {
            model.module_id: model
            for model in self.session.execute(sa.select(ModuleInstallORM)).scalars().all()
        }

        for record in snapshot.installs:
            model = existing_installs.get(record.module_id)
            if model is None:
                model = ModuleInstallORM(id=record.id, module_id=record.module_id)
                self.session.add(model)
            model.module_version = record.module_version
            model.desired_state = record.desired_state
            model.lifecycle_state = record.lifecycle_state
            model.runtime_mode = record.runtime_mode
            model.manifest_ref = record.manifest_ref.model_dump(mode="json")
            model.config_binding_id = record.config_binding_id
            model.installed_at = record.installed_at
            model.enabled_at = record.enabled_at
            model.disabled_at = record.disabled_at
            model.last_error = record.last_error

        for module_id, model in existing_installs.items():
            if module_id in current_module_ids:
                continue
            model.desired_state = "disabled"
            model.lifecycle_state = "removed"
            model.disabled_at = generated_at
            model.last_error = "Manifest no longer discovered."

        self.session.flush()
        install_ids = [record.id for record in snapshot.installs]
        if install_ids:
            for orm_model in (HookContributionORM, EventSubscriptionORM, HealthReportORM):
                self.session.execute(sa.delete(orm_model).where(orm_model.module_install_id.in_(install_ids)))

        for record in snapshot.hooks:
            self.session.add(
                HookContributionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    hook_name=record.hook_name,
                    implementation_ref=record.implementation_ref,
                    execution_order=record.execution_order,
                    timeout_ms=record.timeout_ms,
                    side_effects=record.side_effects,
                    enabled=record.enabled,
                    created_at=record.created_at,
                )
            )
        for record in snapshot.subscriptions:
            self.session.add(
                EventSubscriptionORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    event_type=record.event_type,
                    consumer_group=record.consumer_group,
                    delivery_mode=record.delivery_mode,
                    status=record.status,
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
            )
        for record in snapshot.health:
            self.session.add(
                HealthReportORM(
                    id=record.id,
                    module_install_id=record.module_install_id,
                    status=record.status,
                    summary=record.summary,
                    details_ref=record.details_ref.model_dump(mode="json") if record.details_ref else None,
                    observed_at=record.observed_at,
                )
            )
        self.session.flush()

    def build_snapshot(self, manifests: list[ModuleManifestSummary], generated_at: datetime) -> ModuleCatalogSnapshot:
        module_ids = [manifest.module_id for manifest in manifests]
        installs = self.session.execute(
            sa.select(ModuleInstallORM).where(ModuleInstallORM.module_id.in_(module_ids)).order_by(ModuleInstallORM.module_id.asc())
        ).scalars().all()
        install_ids = [record.id for record in installs]
        hooks = []
        subscriptions = []
        health = []
        if install_ids:
            hooks = self.session.execute(
                sa.select(HookContributionORM).where(HookContributionORM.module_install_id.in_(install_ids)).order_by(HookContributionORM.hook_name.asc())
            ).scalars().all()
            subscriptions = self.session.execute(
                sa.select(EventSubscriptionORM).where(EventSubscriptionORM.module_install_id.in_(install_ids)).order_by(EventSubscriptionORM.event_type.asc())
            ).scalars().all()
            health = self.session.execute(
                sa.select(HealthReportORM).where(HealthReportORM.module_install_id.in_(install_ids)).order_by(HealthReportORM.module_install_id.asc())
            ).scalars().all()
        return ModuleCatalogSnapshot(
            generatedAt=generated_at,
            manifests=manifests,
            installs=[_module_install_record(model) for model in installs],
            hooks=[_hook_record(model) for model in hooks],
            subscriptions=[_subscription_record(model) for model in subscriptions],
            health=[_health_record(model) for model in health],
        )


class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_event(self, payload: dict[str, Any]) -> OutboxRecord:
        record = OutboxRecord(
            id=str(payload.get("id") or new_id("outbox", payload.get("aggregateType"), payload.get("aggregateId"), utc_now().isoformat())),
            projectId=str(payload.get("projectId")) if payload.get("projectId") is not None else None,
            aggregateType=str(payload.get("aggregateType") or "unknown"),
            aggregateId=str(payload.get("aggregateId") or "unknown"),
            eventType=str(payload.get("eventType") or "unknown"),
            eventVersion=int(payload.get("eventVersion", 1)),
            payloadRef=_external_ref(payload.get("payloadRef") or {"type": "package-entry", "locator": "system/unknown"}),
            publishStatus=str(payload.get("publishStatus") or "pending"),
            attempts=int(payload.get("attempts", 0)),
            availableAt=payload.get("availableAt") or utc_now(),
            publishedAt=payload.get("publishedAt"),
            lastError=str(payload.get("lastError")) if payload.get("lastError") is not None else None,
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = OutboxRecordORM(
            id=record.id,
            project_id=record.project_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            event_type=record.event_type,
            event_version=record.event_version,
            payload_ref=record.payload_ref.model_dump(mode="json"),
            publish_status=record.publish_status,
            attempts=record.attempts,
            available_at=record.available_at,
            published_at=record.published_at,
            last_error=record.last_error,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return record

    def list_events(self, *, publish_status: str | None = None, limit: int = 100) -> list[OutboxRecord]:
        statement = sa.select(OutboxRecordORM).order_by(OutboxRecordORM.created_at.desc()).limit(limit)
        if publish_status:
            statement = statement.where(OutboxRecordORM.publish_status == publish_status)
        return [_outbox_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_event(self, event_id: str) -> OutboxRecord | None:
        model = self.session.get(OutboxRecordORM, event_id)
        return _outbox_record(model) if model is not None else None

    def claim_events(self, *, limit: int = 100, now: datetime | None = None) -> list[OutboxRecord]:
        current_time = now or utc_now()
        statement = (
            sa.select(OutboxRecordORM)
            .where(OutboxRecordORM.publish_status == "pending")
            .where(OutboxRecordORM.available_at <= current_time)
            .order_by(OutboxRecordORM.created_at.asc())
            .limit(limit)
        )
        models = self.session.execute(statement).scalars().all()
        for model in models:
            model.publish_status = "publishing"
            model.attempts += 1
        self.session.flush()
        return [_outbox_record(model) for model in models]

    def mark_published(self, event_id: str, *, published_at: datetime | None = None) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "published"
        model.published_at = published_at or utc_now()
        model.last_error = None
        self.session.flush()
        return _outbox_record(model)

    def mark_pending(
        self,
        event_id: str,
        *,
        last_error: str | None = None,
        available_at: datetime | None = None,
    ) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "pending"
        model.available_at = available_at or utc_now()
        model.last_error = last_error
        self.session.flush()
        return _outbox_record(model)

    def mark_dead_letter(self, event_id: str, *, last_error: str) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "dead-letter"
        model.last_error = last_error
        self.session.flush()
        return _outbox_record(model)


class CollaborationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_branches(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MemoryBranchRecord]:
        statement = sa.select(MemoryBranchORM).order_by(MemoryBranchORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(MemoryBranchORM.project_id == project_id)
        if space_id is not None:
            statement = statement.where(MemoryBranchORM.space_id == space_id)
        if status is not None:
            statement = statement.where(MemoryBranchORM.status == status)
        return [_branch_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_branch(self, branch_id: str) -> MemoryBranchRecord | None:
        model = self.session.get(MemoryBranchORM, branch_id)
        return _branch_record(model) if model else None

    def create_branch(self, payload: dict[str, Any]) -> MemoryBranchRecord:
        now = utc_now()
        actor = _actor(payload.get("createdBy"), default_type="agent", default_id="subagent")
        branch_id = str(payload.get("id") or new_id("branch", payload.get("name") or now.isoformat()))
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        space_id = str(payload.get("spaceId") or DEFAULT_SPACE_ID)
        if self.session.get(MemoryBranchORM, branch_id) is not None:
            raise ValueError(f"Branch {branch_id} already exists.")
        branch = MemoryBranchORM(
            id=branch_id,
            project_id=project_id,
            space_id=space_id,
            name=str(payload.get("name") or branch_id),
            base_branch_id=str(payload["baseBranchId"]) if payload.get("baseBranchId") is not None else None,
            head_ref=str(payload["headRef"]) if payload.get("headRef") is not None else None,
            status=str(payload.get("status") or "active"),
            created_at=now,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(branch)
        self.session.flush()
        _ensure_branch_roots(
            self.session,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            created_by=actor,
            now=now,
        )
        return _branch_record(branch)

    def update_branch(self, branch_id: str, payload: dict[str, Any]) -> MemoryBranchRecord:
        branch = self.session.get(MemoryBranchORM, branch_id)
        if branch is None:
            raise KeyError(branch_id)
        if "name" in payload:
            branch.name = str(payload["name"])
        if "baseBranchId" in payload:
            branch.base_branch_id = str(payload["baseBranchId"]) if payload["baseBranchId"] is not None else None
        if "headRef" in payload:
            branch.head_ref = str(payload["headRef"]) if payload["headRef"] is not None else None
        if "status" in payload:
            branch.status = str(payload["status"])
        self.session.flush()
        return _branch_record(branch)

    def list_pull_requests(
        self,
        *,
        project_id: str | None = None,
        source_branch_id: str | None = None,
        target_branch_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[PullRequestRecord]:
        statement = sa.select(PullRequestORM).order_by(PullRequestORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(PullRequestORM.project_id == project_id)
        if source_branch_id is not None:
            statement = statement.where(PullRequestORM.source_branch_id == source_branch_id)
        if target_branch_id is not None:
            statement = statement.where(PullRequestORM.target_branch_id == target_branch_id)
        if status is not None:
            statement = statement.where(PullRequestORM.status == status)
        return [_pull_request_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_pull_request(self, pr_id: str) -> PullRequestRecord | None:
        model = self.session.get(PullRequestORM, pr_id)
        return _pull_request_record(model) if model else None

    def update_pull_request(self, pr_id: str, payload: dict[str, Any]) -> PullRequestRecord:
        model = self.session.get(PullRequestORM, pr_id)
        if model is None:
            raise KeyError(pr_id)
        if "title" in payload:
            model.title = str(payload["title"])
        if "summary" in payload:
            model.summary = str(payload["summary"])
        if "status" in payload:
            model.status = str(payload["status"])
        if "reviewedBy" in payload:
            reviewed_by = payload["reviewedBy"]
            model.reviewed_by = _actor(reviewed_by).model_dump(mode="json") if reviewed_by is not None else None
        if "externalId" in payload:
            model.external_id = str(payload["externalId"]) if payload["externalId"] is not None else None
        if "externalUrl" in payload:
            model.external_url = str(payload["externalUrl"]) if payload["externalUrl"] is not None else None
        if "mergeCommitRef" in payload:
            model.merge_commit_ref = str(payload["mergeCommitRef"]) if payload["mergeCommitRef"] is not None else None
        if "mergedAt" in payload:
            model.merged_at = payload["mergedAt"]
        self.session.flush()
        return _pull_request_record(model)

    def list_review_comments(self, pr_id: str, *, limit: int = 200) -> list[ReviewCommentRecord]:
        statement = (
            sa.select(ReviewCommentORM)
            .where(ReviewCommentORM.pr_id == pr_id)
            .order_by(ReviewCommentORM.created_at.asc())
            .limit(limit)
        )
        return [_review_comment_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_pull_request(self, record: PullRequestRecord) -> PullRequestRecord:
        model = self.session.get(PullRequestORM, record.id)
        if model is None:
            model = PullRequestORM(id=record.id)
            self.session.add(model)
        model.project_id = record.project_id
        model.source_branch_id = record.source_branch_id
        model.target_branch_id = record.target_branch_id
        model.title = record.title
        model.summary = record.summary
        model.status = record.status
        model.created_by = record.created_by.model_dump(mode="json")
        model.reviewed_by = record.reviewed_by.model_dump(mode="json") if record.reviewed_by else None
        model.external_id = record.external_id
        model.external_url = record.external_url
        model.merge_commit_ref = record.merge_commit_ref
        model.merged_at = record.merged_at
        model.created_at = record.created_at
        self.session.flush()
        return _pull_request_record(model)

    def add_review_comment(self, record: ReviewCommentRecord) -> ReviewCommentRecord:
        model = ReviewCommentORM(
            id=record.id,
            pr_id=record.pr_id,
            author=record.author.model_dump(mode="json"),
            target_kind=record.target_kind,
            target_id=record.target_id,
            body=record.body,
            status=record.status,
            created_at=record.created_at,
            resolved_at=record.resolved_at,
        )
        self.session.add(model)
        self.session.flush()
        return _review_comment_record(model)