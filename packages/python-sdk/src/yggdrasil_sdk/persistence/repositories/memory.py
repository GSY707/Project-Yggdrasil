from ._common import *
from ..write_queue import run_serialized_write

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
        branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)

        def _create() -> NodeRecord:
            now = utc_now()
            actor = _actor(payload.get("createdBy") or payload.get("updatedBy"), default_type="user", default_id="core-api")
            node_id = str(payload.get("id") or new_id("node", branch_id, payload.get("title") or now.isoformat()))
            version_id = str(payload.get("latestVersionId") or new_id("ver", node_id, 1, stable=True))
            parent_id = payload.get("parentId")
            project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
            space_id = str(payload.get("spaceId") or DEFAULT_SPACE_ID)
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
                window_index=max(int(payload.get("windowIndex", 1)), 1),
                source_work_tree_node_id=str(payload.get("sourceWorkTreeNodeId")) if payload.get("sourceWorkTreeNodeId") is not None else None,
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

        return run_serialized_write(f"nodes:{branch_id}", _create)

    def create_edge(self, payload: dict[str, Any]) -> EdgeRecord:
        queue_branch_id = str(payload.get("branchId") or DEFAULT_BRANCH_ID)

        def _create() -> EdgeRecord:
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

        return run_serialized_write(f"nodes:{queue_branch_id}", _create)

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
        if "windowIndex" in payload:
            node.window_index = max(int(payload["windowIndex"]), 1)
        if "sourceWorkTreeNodeId" in payload:
            node.source_work_tree_node_id = str(payload["sourceWorkTreeNodeId"]) if payload["sourceWorkTreeNodeId"] is not None else None
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
        def _replace() -> list[ImportFragmentRecord]:
            if self.session.get(ImportJobORM, import_job_id) is None:
                raise KeyError(f"Import job {import_job_id} not found.")

            self.session.execute(sa.delete(ImportFragmentORM).where(ImportFragmentORM.import_job_id == import_job_id))
            created_at = utc_now()
            rows: list[dict[str, Any]] = []
            for index, fragment in enumerate(fragments, start=1):
                raw_ref = _external_ref(fragment.get("rawRef")) or ExternalRef(
                    type="package-entry",
                    locator=f"core-api/memory/import-jobs/{import_job_id}/fragments/{index}",
                )
                normalized_text = str(fragment.get("normalizedText") or fragment.get("text") or "")
                rows.append(
                    {
                        "id": str(fragment.get("id") or new_id("frag", import_job_id, index, stable=True)),
                        "import_job_id": import_job_id,
                        "ordinal": int(fragment.get("ordinal") or index),
                        "raw_ref": raw_ref.model_dump(mode="json"),
                        "normalized_text": normalized_text,
                        "approx_tokens": int(fragment.get("approxTokens") or max(len(normalized_text) // 4, 1)),
                        "related_hints": [str(hint) for hint in fragment.get("relatedHints") or []],
                        "created_at": created_at,
                    }
                )

            if rows:
                self.session.execute(sa.insert(ImportFragmentORM), rows)

            statement = (
                sa.select(ImportFragmentORM)
                .where(ImportFragmentORM.import_job_id == import_job_id)
                .order_by(ImportFragmentORM.ordinal.asc())
            )
            models = self.session.execute(statement).scalars().all()
            return [_import_fragment_record(model) for model in models]

        return run_serialized_write(f"import-fragments:{import_job_id}", _replace)

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
            reverse_trace_mode=bool(payload.get("reverseTraceMode", False)),
            work_tree_node_id=str(payload.get("workTreeNodeId")) if payload.get("workTreeNodeId") is not None else None,
            window_index=int(payload["windowIndex"]) if payload.get("windowIndex") is not None else None,
            token_budget=int(payload["tokenBudget"]) if payload.get("tokenBudget") is not None else None,
            created_at=now,
        )
        self.session.add(model)
        self.session.flush()
        return _retrieval_request_record(model)

