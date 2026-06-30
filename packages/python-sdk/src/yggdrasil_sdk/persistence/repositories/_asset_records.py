from ._imports import (
    AssetEmbeddingORM,
    AssetEmbeddingRecord,
    AssetORM,
    AssetRecord,
    AssetSegmentORM,
    AssetSegmentRecord,
    DatasetVersionORM,
    DatasetVersionRecord,
    EvaluationRunORM,
    EvaluationRunRecord,
    EvaluationSuiteORM,
    EvaluationSuiteRecord,
    ModelArtifactORM,
    ModelArtifactRecord,
)
from ._record_helpers import _actor, _external_ref


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


__all__ = [name for name in globals() if name.startswith("_") and name.endswith("_record")]
