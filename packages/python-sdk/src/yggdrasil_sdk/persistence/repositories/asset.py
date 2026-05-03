from ._common import *

class AssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_assets(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        branch_id: str | None = None,
        owner_node_id: str | None = None,
        media_type: str | None = None,
        limit: int = 100,
    ) -> list[AssetRecord]:
        statement = sa.select(AssetORM).order_by(AssetORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(AssetORM.project_id == project_id)
        if space_id is not None:
            statement = statement.where(AssetORM.space_id == space_id)
        if branch_id is not None:
            statement = statement.where(AssetORM.branch_id == branch_id)
        if owner_node_id is not None:
            statement = statement.where(AssetORM.owner_node_id == owner_node_id)
        if media_type is not None:
            statement = statement.where(AssetORM.media_type == media_type)
        return [_asset_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_asset(self, asset_id: str) -> AssetRecord | None:
        model = self.session.get(AssetORM, asset_id)
        return _asset_record(model) if model is not None else None

    def create_asset(self, payload: dict[str, Any]) -> AssetRecord:
        record = AssetRecord(
            id=str(payload.get("id") or new_id("asset", payload.get("mediaType") or utc_now().isoformat())),
            projectId=str(payload.get("projectId") or DEFAULT_PROJECT_ID),
            spaceId=str(payload.get("spaceId") or DEFAULT_SPACE_ID),
            branchId=str(payload.get("branchId") or DEFAULT_BRANCH_ID),
            ownerNodeId=str(payload.get("ownerNodeId")) if payload.get("ownerNodeId") is not None else None,
            mediaType=str(payload.get("mediaType") or "document"),
            role=str(payload.get("role") or "original"),
            storageKey=str(payload.get("storageKey") or ""),
            checksum=str(payload.get("checksum") or ""),
            sourceRef=_external_ref(payload.get("sourceRef")),
            durationMs=int(payload["durationMs"]) if payload.get("durationMs") is not None else None,
            width=int(payload["width"]) if payload.get("width") is not None else None,
            height=int(payload["height"]) if payload.get("height") is not None else None,
            createdAt=payload.get("createdAt") or utc_now(),
            createdBy=_actor(payload.get("createdBy"), default_type="module", default_id="multimodal-memory"),
        )
        model = AssetORM(
            id=record.id,
            project_id=record.project_id,
            space_id=record.space_id,
            branch_id=record.branch_id,
            owner_node_id=record.owner_node_id,
            media_type=record.media_type,
            role=record.role,
            storage_key=record.storage_key,
            checksum=record.checksum,
            source_ref=record.source_ref.model_dump(mode="json") if record.source_ref else None,
            duration_ms=record.duration_ms,
            width=record.width,
            height=record.height,
            created_at=record.created_at,
            created_by=record.created_by.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.flush()
        return _asset_record(model)

    def replace_asset_segments(self, asset_id: str, segments: list[dict[str, Any]]) -> list[AssetSegmentRecord]:
        if self.session.get(AssetORM, asset_id) is None:
            raise KeyError(asset_id)
        self.session.execute(sa.delete(AssetSegmentORM).where(AssetSegmentORM.asset_id == asset_id))
        created_at = utc_now()
        created: list[AssetSegmentORM] = []
        for index, segment in enumerate(segments, start=1):
            model = AssetSegmentORM(
                id=str(segment.get("id") or new_id("assetseg", asset_id, index, stable=True)),
                asset_id=asset_id,
                ordinal=int(segment.get("ordinal") or index),
                start_offset=int(segment.get("startOffset") or 0),
                end_offset=int(segment.get("endOffset") or segment.get("startOffset") or 0),
                text_excerpt=str(segment.get("textExcerpt")) if segment.get("textExcerpt") is not None else None,
                summary=str(segment.get("summary")) if segment.get("summary") is not None else None,
                embedding_id=str(segment.get("embeddingId")) if segment.get("embeddingId") is not None else None,
                created_at=segment.get("createdAt") or created_at,
            )
            self.session.add(model)
            created.append(model)
        self.session.flush()
        return [_asset_segment_record(model) for model in sorted(created, key=lambda item: item.ordinal)]

    def list_asset_segments(self, asset_id: str, limit: int = 500) -> list[AssetSegmentRecord]:
        statement = sa.select(AssetSegmentORM).where(AssetSegmentORM.asset_id == asset_id).order_by(AssetSegmentORM.ordinal.asc()).limit(limit)
        return [_asset_segment_record(model) for model in self.session.execute(statement).scalars().all()]

    def create_embedding(self, payload: dict[str, Any]) -> AssetEmbeddingRecord:
        record = AssetEmbeddingRecord(
            id=str(payload.get("id") or new_id("embedding", payload.get("ownerKind") or "asset", payload.get("ownerId") or utc_now().isoformat())),
            ownerKind=str(payload.get("ownerKind") or "asset"),
            ownerId=str(payload.get("ownerId") or ""),
            model=str(payload.get("model") or "keyword-hash-v1"),
            dimension=int(payload.get("dimension") or 0),
            vectorRef=_external_ref(payload.get("vectorRef")),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = AssetEmbeddingORM(
            id=record.id,
            owner_kind=record.owner_kind,
            owner_id=record.owner_id,
            model=record.model,
            dimension=record.dimension,
            vector_ref=record.vector_ref.model_dump(mode="json"),
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _asset_embedding_record(model)

    def list_embeddings(
        self,
        *,
        owner_kind: str | None = None,
        owner_id: str | None = None,
        limit: int = 500,
    ) -> list[AssetEmbeddingRecord]:
        statement = sa.select(AssetEmbeddingORM).order_by(AssetEmbeddingORM.created_at.desc()).limit(limit)
        if owner_kind is not None:
            statement = statement.where(AssetEmbeddingORM.owner_kind == owner_kind)
        if owner_id is not None:
            statement = statement.where(AssetEmbeddingORM.owner_id == owner_id)
        return [_asset_embedding_record(model) for model in self.session.execute(statement).scalars().all()]

