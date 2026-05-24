from ._imports import *  # noqa: F403,F401
from ._records_part_a import *  # noqa: F403,F401

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
