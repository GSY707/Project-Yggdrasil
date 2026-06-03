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
        windowIndex=model.window_index,
        sourceWorkTreeNodeId=model.source_work_tree_node_id,
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
        reverseTraceMode=model.reverse_trace_mode,
        workTreeNodeId=model.work_tree_node_id,
        windowIndex=model.window_index,
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
        windowIndex=model.window_index,
        restartCount=model.restart_count,
        cumulativeWindowSpanTokens=model.cumulative_window_span_tokens,
        carryForwardLossCount=model.carry_forward_loss_count,
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
        windowIndex=model.window_index,
        restartCount=model.restart_count,
        cumulativeWindowSpanTokens=model.cumulative_window_span_tokens,
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
        currentNodeId=model.current_node_id,
        workingNodeAnnotation=model.working_node_annotation,
        pcMemo=model.pc_memo,
        topFrameId=model.top_frame_id,
        stackDigest=model.stack_digest,
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

def _model_invocation_record(model: ModelInvocationORM) -> ModelInvocationRecord:
    return ModelInvocationRecord(
        id=model.id,
        appId=model.app_id,
        projectId=model.project_id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        routeDecisionId=model.route_decision_id,
        requestedModel=model.requested_model,
        requestedProvider=model.requested_provider,
        resolvedModel=model.resolved_model,
        resolvedProvider=model.resolved_provider,
        invocationKind=model.invocation_kind,
        status=model.status,
        traceId=model.trace_id,
        promptCompileArtifactId=model.prompt_compile_artifact_id,
        requestRef=_external_ref(model.request_ref),
        responseRef=_external_ref(model.response_ref),
        outputLabels=[str(label) for label in model.output_labels or []],
        assistantTextSummary=model.assistant_text_summary,
        inputTokensUsed=model.input_tokens_used,
        outputTokensUsed=model.output_tokens_used,
        costUsed=model.cost_used,
        latencyMs=model.latency_ms,
        errorSummary=model.error_summary,
        startedAt=model.started_at,
        endedAt=model.ended_at,
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


def _mailbox_message_record(model: MailboxMessageORM) -> MailboxMessageRecord:
    return MailboxMessageRecord(
        id=model.id,
        projectId=model.project_id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        sender=_actor(model.sender),
        messageKind=model.message_kind,
        subject=model.subject,
        body=model.body,
        workTreeNodeId=model.work_tree_node_id,
        wakeOnMessage=model.wake_on_message,
        status=model.status,
        payloadRef=_external_ref(model.payload_ref),
        createdAt=model.created_at,
        deliveredAt=model.delivered_at,
        acknowledgedAt=model.acknowledged_at,
    )


def _side_channel_event_record(model: SideChannelEventORM) -> SideChannelEventRecord:
    return SideChannelEventRecord(
        id=model.id,
        projectId=model.project_id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        source=_actor(model.source),
        eventKind=model.event_kind,
        level=model.level,
        summary=model.summary,
        workTreeNodeId=model.work_tree_node_id,
        payloadRef=_external_ref(model.payload_ref),
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

def _evaluation_suite_record(model: EvaluationSuiteORM) -> EvaluationSuiteRecord:
    return EvaluationSuiteRecord(
        id=model.id,
        name=model.name,
        domain=model.domain,
        metricRefs=list(model.metric_refs or []),
        createdAt=model.created_at,
    )

def _evaluation_run_record(model: EvaluationRunORM) -> EvaluationRunRecord:
    return EvaluationRunRecord(
        id=model.id,
        suiteId=model.suite_id,
        projectId=model.project_id,
        subjectKind=model.subject_kind,
        subjectRef=model.subject_ref,
        status=model.status,
        metricsRef=_external_ref(model.metrics_ref),
        startedAt=model.started_at,
        endedAt=model.ended_at,
        createdAt=model.created_at,
    )

def _asset_record(model: AssetORM) -> AssetRecord:
    return AssetRecord(
        id=model.id,
        projectId=model.project_id,
        spaceId=model.space_id,
        branchId=model.branch_id,
        ownerNodeId=model.owner_node_id,
        mediaType=model.media_type,
        role=model.role,
        storageKey=model.storage_key,
        checksum=model.checksum,
        sourceRef=_external_ref(model.source_ref),
        relatedWorkTreeNodeIds=[str(node_id) for node_id in model.related_work_tree_node_ids or []],
        durationMs=model.duration_ms,
        width=model.width,
        height=model.height,
        createdAt=model.created_at,
        createdBy=_actor(model.created_by),
    )

def _asset_segment_record(model: AssetSegmentORM) -> AssetSegmentRecord:
    return AssetSegmentRecord(
        id=model.id,
        assetId=model.asset_id,
        ordinal=model.ordinal,
        startOffset=model.start_offset,
        endOffset=model.end_offset,
        textExcerpt=model.text_excerpt,
        summary=model.summary,
        embeddingId=model.embedding_id,
        createdAt=model.created_at,
    )

def _asset_embedding_record(model: AssetEmbeddingORM) -> AssetEmbeddingRecord:
    return AssetEmbeddingRecord(
        id=model.id,
        ownerKind=model.owner_kind,
        ownerId=model.owner_id,
        model=model.model,
        dimension=model.dimension,
        vectorRef=_external_ref(model.vector_ref),
        createdAt=model.created_at,
    )

def _dataset_version_record(model: DatasetVersionORM) -> DatasetVersionRecord:
    return DatasetVersionRecord(
        id=model.id,
        datasetName=model.dataset_name,
        version=model.version,
        sourceFilter=dict(model.source_filter or {}),
        storageKey=model.storage_key,
        rowCount=model.row_count,
        createdAt=model.created_at,
    )

def _model_artifact_record(model: ModelArtifactORM) -> ModelArtifactRecord:
    return ModelArtifactRecord(
        id=model.id,
        baseModel=model.base_model,
        tuningMethod=model.tuning_method,
        datasetVersionId=model.dataset_version_id,
        metricsRef=_external_ref(model.metrics_ref),
        storageKey=model.storage_key,
        status=model.status,
        createdAt=model.created_at,
    )

def _prompt_profile_version_record(model: PromptProfileVersionORM) -> PromptProfileVersionRecord:
    return PromptProfileVersionRecord(
        id=model.id,
        promptProfileId=model.prompt_profile_id,
        name=model.name,
        version=model.version,
        runScope=model.run_scope,
        body=dict(model.body or {}),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )

def _seed_template_version_record(model: SeedTemplateVersionORM) -> SeedTemplateVersionRecord:
    return SeedTemplateVersionRecord(
        id=model.id,
        seedTemplateId=model.seed_template_id,
        name=model.name,
        version=model.version,
        domain=model.domain,
        scenario=model.scenario,
        body=dict(model.body or {}),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )

def _prompt_compile_artifact_record(model: PromptCompileArtifactORM) -> PromptCompileArtifactRecord:
    return PromptCompileArtifactRecord(
        id=model.id,
        appId=model.app_id,
        projectId=model.project_id,
        taskId=model.task_id,
        agentRunId=model.agent_run_id,
        modelInvocationId=model.model_invocation_id,
        promptProfileVersionId=model.prompt_profile_version_id,
        seedTemplateVersionId=model.seed_template_version_id,
        runType=model.run_type,
        taskType=model.task_type,
        scenario=model.scenario,
        registeredTools=list(model.registered_tools or []),
        bootSections=dict(model.boot_sections or {}),
        systemSections=dict(model.system_sections or {}),
        userSections=dict(model.user_sections or {}),
        workTreeSnapshot=dict(model.work_tree_snapshot or {}) if model.work_tree_snapshot is not None else None,
        takeoverProtocolSnapshot=dict(model.takeover_protocol_snapshot or {}) if model.takeover_protocol_snapshot is not None else None,
        compiledMessagesRef=_external_ref(model.compiled_messages_ref),
        contentHash=model.content_hash,
        createdAt=model.created_at,
    )

__all__ = [name for name in globals() if not name.startswith("__")]
