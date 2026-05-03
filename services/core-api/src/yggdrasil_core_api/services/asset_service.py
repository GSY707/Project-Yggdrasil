from ._base import *  # noqa: F403,F401

class AssetServiceMixin:
    def list_assets(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        branch_id: str | None = None,
        owner_node_id: str | None = None,
        media_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            assets = AssetRepository(session).list_assets(
                project_id=project_id,
                space_id=space_id,
                branch_id=branch_id,
                owner_node_id=owner_node_id,
                media_type=media_type,
                limit=limit,
            )
        return {"assets": [asset.model_dump(by_alias=True, mode="json") for asset in assets]}

    def get_asset(self, asset_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = AssetRepository(session)
            asset = repository.get_asset(asset_id)
            if asset is None:
                raise KeyError(asset_id)
            segments = repository.list_asset_segments(asset_id, limit=1000)
            segment_ids = {segment.id for segment in segments}
            embeddings = [
                embedding
                for embedding in repository.list_embeddings(owner_kind="asset-segment", limit=max(len(segment_ids) * 4, 200))
                if embedding.owner_id in segment_ids
            ]
            asset_embeddings = repository.list_embeddings(owner_kind="asset", owner_id=asset_id, limit=100)
        return {
            "asset": asset.model_dump(by_alias=True, mode="json"),
            "segments": [segment.model_dump(by_alias=True, mode="json") for segment in segments],
            "embeddings": [embedding.model_dump(by_alias=True, mode="json") for embedding in [*asset_embeddings, *embeddings]],
            "sourcePayload": self._load_ref_payload(asset.source_ref.locator if asset.source_ref else None),
        }

    def ingest_asset(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule

        result = MultimodalMemoryModule().ingest_asset(payload)
        return result

    def list_dataset_versions(
        self,
        *,
        dataset_name: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            versions = TrainingRepository(session).list_dataset_versions(dataset_name=dataset_name, limit=limit)
        return {"datasetVersions": [version.model_dump(by_alias=True, mode="json") for version in versions]}

    def get_dataset_version(self, dataset_version_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = TrainingRepository(session)
            dataset_version = repository.get_dataset_version(dataset_version_id)
            if dataset_version is None:
                raise KeyError(dataset_version_id)
            model_artifacts = repository.list_model_artifacts(dataset_version_id=dataset_version_id, limit=200)
        return {
            "datasetVersion": dataset_version.model_dump(by_alias=True, mode="json"),
            "modelArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in model_artifacts],
            "previewRows": self._load_jsonl_preview(dataset_version.storage_key, limit=5),
        }

    def prepare_dataset_version(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_training_lab.plugin import TrainingLabModule

        return TrainingLabModule().prepare_dataset(payload)

    def list_model_artifacts(
        self,
        *,
        dataset_version_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            artifacts = TrainingRepository(session).list_model_artifacts(
                dataset_version_id=dataset_version_id,
                status=status,
                limit=limit,
            )
        return {"modelArtifacts": [artifact.model_dump(by_alias=True, mode="json") for artifact in artifacts]}

    def get_model_artifact(self, artifact_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = TrainingRepository(session)
            artifact = repository.get_model_artifact(artifact_id)
            if artifact is None:
                raise KeyError(artifact_id)
            dataset_version = repository.get_dataset_version(artifact.dataset_version_id)
        return {
            "modelArtifact": artifact.model_dump(by_alias=True, mode="json"),
            "datasetVersion": dataset_version.model_dump(by_alias=True, mode="json") if dataset_version is not None else None,
            "metrics": self._load_metrics_payload(artifact.metrics_ref.locator if artifact.metrics_ref else None),
        }

    def stage_model_artifact(self, payload: dict[str, Any]) -> dict[str, object]:
        from yggdrasil_training_lab.plugin import TrainingLabModule

        return TrainingLabModule().stage_model_artifact(payload)


