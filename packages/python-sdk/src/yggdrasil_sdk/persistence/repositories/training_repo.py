from ._common import *  # noqa: F403,F401

class TrainingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_dataset_version(self, payload: dict[str, Any]) -> DatasetVersionRecord:
        record = DatasetVersionRecord(
            id=str(payload.get("id") or new_id("dataset", payload.get("datasetName") or utc_now().isoformat())),
            datasetName=str(payload.get("datasetName") or "dataset"),
            version=str(payload.get("version") or "v1"),
            sourceFilter=dict(payload.get("sourceFilter") or {}),
            storageKey=str(payload.get("storageKey") or ""),
            rowCount=int(payload.get("rowCount") or 0),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = DatasetVersionORM(
            id=record.id,
            dataset_name=record.dataset_name,
            version=record.version,
            source_filter=dict(record.source_filter),
            storage_key=record.storage_key,
            row_count=record.row_count,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _dataset_version_record(model)

    def get_dataset_version(self, dataset_version_id: str) -> DatasetVersionRecord | None:
        model = self.session.get(DatasetVersionORM, dataset_version_id)
        return _dataset_version_record(model) if model is not None else None

    def list_dataset_versions(self, *, dataset_name: str | None = None, limit: int = 100) -> list[DatasetVersionRecord]:
        statement = sa.select(DatasetVersionORM).order_by(DatasetVersionORM.created_at.desc()).limit(limit)
        if dataset_name is not None:
            statement = statement.where(DatasetVersionORM.dataset_name == dataset_name)
        return [_dataset_version_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_model_artifact(self, artifact_id: str) -> ModelArtifactRecord | None:
        model = self.session.get(ModelArtifactORM, artifact_id)
        return _model_artifact_record(model) if model is not None else None

    def create_model_artifact(self, payload: dict[str, Any]) -> ModelArtifactRecord:
        dataset_version_id = str(payload.get("datasetVersionId") or "")
        if not dataset_version_id:
            raise KeyError("datasetVersionId")
        if self.session.get(DatasetVersionORM, dataset_version_id) is None:
            raise KeyError(dataset_version_id)
        record = ModelArtifactRecord(
            id=str(payload.get("id") or new_id("modelart", payload.get("baseModel") or dataset_version_id, utc_now().isoformat())),
            baseModel=str(payload.get("baseModel") or "unknown-base-model"),
            tuningMethod=str(payload.get("tuningMethod") or "distillation"),
            datasetVersionId=dataset_version_id,
            metricsRef=_external_ref(payload.get("metricsRef")),
            storageKey=str(payload.get("storageKey") or ""),
            status=str(payload.get("status") or "staged"),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = ModelArtifactORM(
            id=record.id,
            base_model=record.base_model,
            tuning_method=record.tuning_method,
            dataset_version_id=record.dataset_version_id,
            metrics_ref=record.metrics_ref.model_dump(mode="json") if record.metrics_ref else None,
            storage_key=record.storage_key,
            status=record.status,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _model_artifact_record(model)

    def update_model_artifact(self, artifact_id: str, payload: dict[str, Any]) -> ModelArtifactRecord:
        model = self.session.get(ModelArtifactORM, artifact_id)
        if model is None:
            raise KeyError(artifact_id)
        if "metricsRef" in payload:
            metrics_ref = _external_ref(payload.get("metricsRef"))
            model.metrics_ref = metrics_ref.model_dump(mode="json") if metrics_ref is not None else None
        if "status" in payload:
            model.status = str(payload.get("status") or model.status)
        if "storageKey" in payload:
            model.storage_key = str(payload.get("storageKey") or model.storage_key)
        self.session.flush()
        return _model_artifact_record(model)

    def list_model_artifacts(
        self,
        *,
        dataset_version_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ModelArtifactRecord]:
        statement = sa.select(ModelArtifactORM).order_by(ModelArtifactORM.created_at.desc()).limit(limit)
        if dataset_version_id is not None:
            statement = statement.where(ModelArtifactORM.dataset_version_id == dataset_version_id)
        if status is not None:
            statement = statement.where(ModelArtifactORM.status == status)
        return [_model_artifact_record(model) for model in self.session.execute(statement).scalars().all()]


__all__ = [name for name in globals() if not name.startswith("__")]
