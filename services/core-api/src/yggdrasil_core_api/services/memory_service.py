from ._base import *  # noqa: F403,F401

class MemoryServiceMixin:
    def list_spaces(
        self,
        *,
        project_id: str | None = None,
        space_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            spaces = CollaborationRepository(session).list_spaces(
                project_id=project_id,
                space_type=space_type,
                status=status,
                limit=limit,
            )
        return {"spaces": [space.model_dump(by_alias=True, mode="json") for space in spaces]}

    def create_space(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            space = CollaborationRepository(session).create_space(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": space.project_id,
                    "aggregateType": "space",
                    "aggregateId": space.id,
                    "eventType": "space.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/spaces/{space.id}"},
                }
            )
        return {
            "space": space.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_nodes(self, *, branch_id: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            nodes = NodeRepository(session).list_nodes(branch_id=branch_id, limit=limit)
        return {"nodes": [node.model_dump(by_alias=True, mode="json") for node in nodes]}

    def get_node(self, node_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            node = repository.get_node(node_id)
            if node is None:
                raise KeyError(node_id)
            versions = repository.list_versions(node_id)
            annotations = repository.list_source_annotations(owner_kind="node", owner_id=node_id, limit=500)
            edges = repository.list_edges(node_id=node_id, limit=500)
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "versions": [version.model_dump(by_alias=True, mode="json") for version in versions],
            "annotations": [annotation.model_dump(by_alias=True, mode="json") for annotation in annotations],
            "outgoingEdges": [edge.model_dump(by_alias=True, mode="json") for edge in edges if edge.from_node_id == node_id],
            "incomingEdges": [edge.model_dump(by_alias=True, mode="json") for edge in edges if edge.to_node_id == node_id],
        }

    def create_node(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node = NodeRepository(session).create_node(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": node.project_id,
                    "aggregateType": "node",
                    "aggregateId": node.id,
                    "eventType": "node.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node.id}"},
                }
            )
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def append_node_version(self, node_id: str, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            version = repository.append_version(node_id, payload)
            node = repository.get_node(node_id)
            if node is None:
                raise KeyError(node_id)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": node.project_id,
                    "aggregateType": "node-version",
                    "aggregateId": version.id,
                    "eventType": "node.version.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node_id}/versions/{version.id}"},
                }
            )
        return {
            "node": node.model_dump(by_alias=True, mode="json"),
            "version": version.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def add_node_annotation(self, node_id: str, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            repository = NodeRepository(session)
            if repository.get_node(node_id) is None:
                raise KeyError(node_id)
            annotation = repository.add_source_annotation("node", node_id, payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": annotation.project_id,
                    "aggregateType": "source-annotation",
                    "aggregateId": annotation.id,
                    "eventType": "source.annotation.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/nodes/{node_id}/annotations/{annotation.id}"},
                }
            )
        return {
            "annotation": annotation.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_branches(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            branches = CollaborationRepository(session).list_branches(
                project_id=project_id,
                space_id=space_id,
                status=status,
                limit=limit,
            )
        return {"branches": [branch.model_dump(by_alias=True, mode="json") for branch in branches]}

    def create_branch(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            branch = CollaborationRepository(session).create_branch(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": branch.project_id,
                    "aggregateType": "branch",
                    "aggregateId": branch.id,
                    "eventType": "branch.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/branches/{branch.id}"},
                }
            )
        return {
            "branch": branch.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_space_mounts(
        self,
        *,
        project_id: str | None = None,
        host_space_id: str | None = None,
        mounted_space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            mounts = CollaborationRepository(session).list_space_mounts(
                project_id=project_id,
                host_space_id=host_space_id,
                mounted_space_id=mounted_space_id,
                status=status,
                limit=limit,
            )
        return {"spaceMounts": [mount.model_dump(by_alias=True, mode="json") for mount in mounts]}

    def create_space_mount(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            mount = CollaborationRepository(session).create_space_mount(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": mount.project_id,
                    "aggregateType": "space-mount",
                    "aggregateId": mount.id,
                    "eventType": "space.mount.created",
                    "payloadRef": {"type": "package-entry", "locator": f"core-api/collaboration/space-mounts/{mount.id}"},
                }
            )
        return {
            "spaceMount": mount.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_permission_tuples(
        self,
        *,
        project_id: str | None = None,
        subject: str | None = None,
        relation: str | None = None,
        resource: str | None = None,
        effect: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            tuples = CollaborationRepository(session).list_permission_tuples(
                project_id=project_id,
                subject=subject,
                relation=relation,
                resource=resource,
                effect=effect,
                limit=limit,
            )
        return {"permissionTuples": [item.model_dump(by_alias=True, mode="json") for item in tuples]}

    def create_permission_tuple(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            permission_tuple = CollaborationRepository(session).create_permission_tuple(payload)
            event = OutboxRepository(session).record_event(
                {
                    "projectId": permission_tuple.project_id,
                    "aggregateType": "permission-tuple",
                    "aggregateId": permission_tuple.id,
                    "eventType": "permission.tuple.created",
                    "payloadRef": {
                        "type": "package-entry",
                        "locator": f"core-api/collaboration/permission-tuples/{permission_tuple.id}",
                    },
                }
            )
        return {
            "permissionTuple": permission_tuple.model_dump(by_alias=True, mode="json"),
            "outboxRecord": event.model_dump(by_alias=True, mode="json"),
        }

    def list_import_jobs(self, *, status: str | None = None, limit: int = 100) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            jobs = MemoryRepository(session).list_import_jobs(status=status, limit=limit)
        return {"importJobs": [job.model_dump(by_alias=True, mode="json") for job in jobs]}

    def get_import_job(self, import_job_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            node_repository = NodeRepository(session)
            import_job = memory_repository.get_import_job(import_job_id)
            if import_job is None:
                raise KeyError(import_job_id)
            fragments = memory_repository.list_import_fragments(import_job_id)
            tree_plans = memory_repository.list_tree_plans(import_job_id)
            latest_tree_plan = tree_plans[0] if tree_plans else None
            node_ids = [str(payload.get("id")) for payload in (latest_tree_plan.candidate_node_payloads if latest_tree_plan else [])]
            edge_ids = {str(payload.get("id")) for payload in (latest_tree_plan.candidate_edge_payloads if latest_tree_plan else [])}
            annotation_ids = {str(payload.get("id")) for payload in (latest_tree_plan.candidate_source_annotations if latest_tree_plan else [])}
            materialized_nodes = [
                record.model_dump(by_alias=True, mode="json")
                for node_id in node_ids
                for record in [node_repository.get_node(node_id)]
                if record is not None
            ]
            materialized_edges = [
                record.model_dump(by_alias=True, mode="json")
                for record in node_repository.list_edges(branch_id=import_job.branch_id, limit=2000)
                if record.id in edge_ids
            ]
            materialized_annotations = [
                record.model_dump(by_alias=True, mode="json")
                for record in node_repository.list_source_annotations(branch_id=import_job.branch_id, limit=2000)
                if record.id in annotation_ids
            ]
        return {
            "importJob": import_job.model_dump(by_alias=True, mode="json"),
            "fragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
            "treePlans": [plan.model_dump(by_alias=True, mode="json") for plan in tree_plans],
            "materializedNodes": materialized_nodes,
            "materializedEdges": materialized_edges,
            "materializedSourceAnnotations": materialized_annotations,
        }

    def create_import_job(self, payload: dict[str, Any]) -> dict[str, object]:
        process_immediately = bool(payload.get("processImmediately", False))
        ordered_fragments = payload.get("orderedFragments") if isinstance(payload.get("orderedFragments"), list) else None
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.create_import_job(payload)
            if ordered_fragments:
                memory_repository.replace_import_fragments(import_job.id, ordered_fragments)
            outbox_record = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="import.accepted",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )
        if process_immediately:
            result = self.process_import_job(import_job.id, payload)
            result["acceptedOutboxRecord"] = outbox_record.model_dump(by_alias=True, mode="json")
            return result
        return {
            "importJob": import_job.model_dump(by_alias=True, mode="json"),
            "outboxRecord": outbox_record.model_dump(by_alias=True, mode="json"),
        }

    def process_import_job(self, import_job_id: str, payload: dict[str, Any] | None = None) -> dict[str, object]:
        request_payload = payload or {}
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.get_import_job(import_job_id)
            if import_job is None:
                raise KeyError(import_job_id)
            if import_job.status == "completed":
                return {"status": "completed", **self.get_import_job(import_job_id)}
            memory_repository.set_import_job_status(import_job_id, "preprocessing")
            existing_fragments = memory_repository.list_import_fragments(import_job_id)

        if isinstance(request_payload.get("orderedFragments"), list):
            preprocess_result = {
                "status": "ok",
                "orderedFragments": request_payload["orderedFragments"],
            }
        elif request_payload.get("sourceText") is not None or isinstance(request_payload.get("sourceTexts"), list):
            preprocess_result = self._call_module_hook(
                "text-memory",
                HookNames.MEMORY_INGEST_PREPROCESS,
                {
                    "importJob": import_job.model_dump(by_alias=True, mode="json"),
                    "importPolicy": import_job.import_policy.model_dump(by_alias=True),
                    "sourceText": request_payload.get("sourceText"),
                    "sourceTexts": request_payload.get("sourceTexts"),
                    "rawRef": request_payload.get("rawRef"),
                },
            )
        elif existing_fragments:
            preprocess_result = {
                "status": "ok",
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in existing_fragments],
            }
        else:
            raise ValueError("Import processing requires sourceText, sourceTexts, orderedFragments, or previously persisted fragments.")

        if str(preprocess_result.get("status") or "ok").lower() == "error":
            with self.runtime.session_scope() as session:
                WorkspaceBootstrapRepository(session).ensure_default_workspace()
                import_job = MemoryRepository(session).set_import_job_status(
                    import_job_id,
                    "failed",
                    failure_reason=str(preprocess_result.get("summary") or "Import preprocessing failed."),
                )
            return {
                "status": "failed",
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
            }

        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.set_import_job_status(import_job_id, "planning")
            fragments = memory_repository.replace_import_fragments(import_job_id, list(preprocess_result.get("orderedFragments") or []))
            segmented_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="import.segmented",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )

        envelope = EventEnvelope(
            eventType="import.accepted",
            eventVersion=1,
            eventId=new_id("evt", "import.accepted", import_job.id),
            occurredAt=utc_now(),
            source="core-api",
            actor=ActorRef(type="system", id="core-api"),
            projectId=import_job.project_id,
            spaceId="space_default",
            branchId=import_job.branch_id,
            correlationId=import_job.id,
            schemaRef="yggdrasil://events/import.accepted/v1",
            payload={
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
                "importPolicy": import_job.import_policy.model_dump(by_alias=True),
            },
        )
        handling_result = self._dispatch_module_event("text-memory", envelope)
        plan_emissions = [event for event in handling_result.emitted_events if event.event_type == "memory.tree.plan.proposed"]
        if not plan_emissions:
            raise RuntimeError("text-memory did not emit memory.tree.plan.proposed.")
        plan_payload = dict(plan_emissions[0].payload)
        plan_payload["importJobId"] = import_job.id
        plan_payload["status"] = "proposed"
        plan_payload["candidateNodePayloads"] = list(plan_payload.pop("candidateNodes", []))
        plan_payload["candidateEdgePayloads"] = list(plan_payload.pop("candidateEdges", []))
        plan_payload["candidateSourceAnnotations"] = list(plan_payload.pop("candidateSourceAnnotations", []))
        plan_payload["proposedBy"] = {"type": "module", "id": "text-memory"}
        confidence = plan_payload.pop("confidence", None)
        if confidence is not None:
            plan_payload["rationale"] = f"{plan_payload.get('rationale', 'Generated tree plan.')} Confidence={confidence}."

        validation_result = self._call_module_hook(
            "text-memory",
            HookNames.MEMORY_WRITE_VALIDATE,
            {
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "orderedFragments": [fragment.model_dump(by_alias=True, mode="json") for fragment in fragments],
                "candidateNodes": plan_payload["candidateNodePayloads"],
                "candidateEdges": plan_payload["candidateEdgePayloads"],
            },
        )
        if str(validation_result.get("status") or "ok").lower() == "error":
            with self.runtime.session_scope() as session:
                WorkspaceBootstrapRepository(session).ensure_default_workspace()
                memory_repository = MemoryRepository(session)
                import_job = memory_repository.set_import_job_status(
                    import_job_id,
                    "failed",
                    failure_reason=str(validation_result.get("summary") or "Memory write validation failed."),
                )
            return {
                "status": "failed",
                "importJob": import_job.model_dump(by_alias=True, mode="json"),
                "validation": validation_result,
            }

        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            import_job = memory_repository.set_import_job_status(import_job_id, "materializing")
            tree_plan = memory_repository.upsert_tree_plan(plan_payload)
            plan_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="tree-plan",
                aggregate_id=tree_plan.id,
                event_type="memory.tree.plan.proposed",
                locator=f"core-api/memory/import-jobs/{import_job.id}/tree-plans/{tree_plan.id}",
            )
            memory_repository.set_tree_plan_status(tree_plan.id, "accepted")
            materialized = self._materialize_tree_plan(session, import_job=import_job, tree_plan=tree_plan)
            memory_repository.set_tree_plan_status(tree_plan.id, "materialized")
            import_job = memory_repository.set_import_job_status(import_job_id, "completed")
            materialized_event = self._record_package_event(
                session,
                project_id=import_job.project_id,
                aggregate_type="import-job",
                aggregate_id=import_job.id,
                event_type="memory.tree.materialized",
                locator=f"core-api/memory/import-jobs/{import_job.id}",
            )

        details = self.get_import_job(import_job_id)
        return {
            "status": "completed",
            **details,
            "validation": validation_result,
            "segmentedOutboxRecord": segmented_event.model_dump(by_alias=True, mode="json"),
            "treePlanOutboxRecord": plan_event.model_dump(by_alias=True, mode="json"),
            "materializedOutboxRecord": materialized_event.model_dump(by_alias=True, mode="json"),
            "materialized": materialized,
        }

    def create_retrieval(self, payload: dict[str, Any]) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            memory_repository = MemoryRepository(session)
            node_repository = NodeRepository(session)
            retrieval_request = memory_repository.create_retrieval_request(payload)
            nodes = node_repository.list_nodes(branch_id=retrieval_request.branch_id, limit=2000)
            edges = node_repository.list_edges(branch_id=retrieval_request.branch_id, limit=4000)
            annotations = node_repository.list_source_annotations(branch_id=retrieval_request.branch_id, limit=4000)
        result = self._call_module_hook(
            "text-memory",
            HookNames.MEMORY_RETRIEVE_EXPAND,
            {
                "retrievalRequest": retrieval_request.model_dump(by_alias=True, mode="json"),
                "nodes": [node.model_dump(by_alias=True, mode="json") for node in nodes],
                "edges": [edge.model_dump(by_alias=True, mode="json") for edge in edges],
                "sourceAnnotations": [annotation.model_dump(by_alias=True, mode="json") for annotation in annotations],
            },
        )
        bundle = RetrievalBundle.model_validate(result)
        return {
            "retrievalRequest": retrieval_request.model_dump(by_alias=True, mode="json"),
            "retrievalBundle": bundle.model_dump(by_alias=True, mode="json"),
        }


