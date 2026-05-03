from ._imports import *  # noqa: F403,F401

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

def _space_mount_record(model: SpaceMountORM) -> SpaceMountRecord:
    return SpaceMountRecord(
        id=model.id,
        projectId=model.project_id,
        hostSpaceId=model.host_space_id,
        mountedSpaceId=model.mounted_space_id,
        mountMode=model.mount_mode,
        status=model.status,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )

def _permission_tuple_record(model: PermissionTupleORM) -> PermissionTupleRecord:
    return PermissionTupleRecord(
        id=model.id,
        projectId=model.project_id,
        subject=model.subject,
        relation=model.relation,
        resource=model.resource,
        condition=dict(model.condition or {}) if model.condition is not None else None,
        effect=model.effect,
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
        appId=model.app_id,
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
        appId=model.app_id,
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
        appId=model.app_id,
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


__all__ = [name for name in globals() if not name.startswith("__")]
