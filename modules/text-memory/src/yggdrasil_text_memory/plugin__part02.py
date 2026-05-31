def update_memory_with_version_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    expected_latest_version_id = str(payload.get("expectedLatestVersionId") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not expected_latest_version_id:
        raise KeyError("expectedLatestVersionId")
    mode = str(payload.get("mode") or "revise").strip().lower()
    if mode not in {"write", "revise", "relate"}:
        raise ValueError(f"Unsupported mode: {mode}")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)

    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            if node.latest_version_id != expected_latest_version_id:
                recent_versions = node_repository.list_versions(node_id, limit=5)
                return {
                    "status": "conflict",
                    "mode": mode,
                    "node": _memory_node_payload(node),
                    "expectedLatestVersionId": expected_latest_version_id,
                    "currentLatestVersionId": node.latest_version_id,
                    "recentVersions": [_memory_version_payload(version) for version in recent_versions],
                    "recommendedActions": [
                        "text_memory.append_memory_log",
                        "text_memory.submit_memory_proposal",
                    ],
                    "summary": normalize_excerpt(
                        f"Version conflict on node {node.title}; latest pointer moved to {node.latest_version_id}.",
                        180,
                    ),
                }

            if mode == "relate":
                related_node_id = str(payload.get("relatedNodeId") or "").strip()
                if not related_node_id:
                    raise KeyError("relatedNodeId")
                related_node = node_repository.get_node(related_node_id)
                if related_node is None:
                    raise KeyError(f"Node {related_node_id} not found.")
                edge = node_repository.create_edge(
                    {
                        "projectId": node.project_id,
                        "spaceId": node.space_id,
                        "branchId": node.branch_id,
                        "fromNodeId": node.id,
                        "toNodeId": related_node.id,
                        "relationType": str(payload.get("relationType") or "related-to"),
                        "reason": str(payload.get("reason") or f"Linked from memory tool at {source_work_tree_node_id or 'no-work-tree'}"),
                        "createdBy": actor,
                        "updatedBy": actor,
                    }
                )
                return {
                    "status": "updated",
                    "mode": mode,
                    "node": _memory_node_payload(node),
                    "edge": edge.model_dump(by_alias=True, mode="json"),
                    "summary": normalize_excerpt(f"Created relation from {node.title} to {related_node.title}.", 160),
                }

            version_payload: dict[str, Any] = {
                "changeReason": str(payload.get("changeReason") or f"memory-tool-{mode}"),
                "createdBy": actor,
                "updatedBy": actor,
                "sourceWorkTreeNodeId": source_work_tree_node_id,
            }
            if payload.get("title") is not None:
                version_payload["title"] = str(payload.get("title") or "")
            if payload.get("content") is not None:
                version_payload["content"] = str(payload.get("content") or "")
            if "title" not in version_payload and "content" not in version_payload:
                raise ValueError("write/revise mode requires title or content.")

            version = node_repository.append_version(node_id, version_payload)
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "updated",
                "mode": mode,
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(f"Updated memory node {node.title} via {mode} mode.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
def append_memory_log_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    log_entry = str(payload.get("logEntry") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not log_entry:
        raise KeyError("logEntry")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            version = node_repository.append_memory_log_entry(
                node_id,
                log_entry,
                {
                    "changeReason": str(payload.get("changeReason") or "append-memory-log"),
                    "createdBy": actor,
                    "updatedBy": actor,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                },
            )
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "appended",
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(
                    f"Appended memory log to node {updated_node.title if updated_node is not None else node_id}.",
                    160,
                ),
            }

    return _run_with_sqlite_lock_retry(_action)
def submit_memory_proposal_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    proposal = str(payload.get("proposal") or "").strip()
    if not node_id:
        raise KeyError("nodeId")
    if not proposal:
        raise KeyError("proposal")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            proposal_node = node_repository.create_node(
                {
                    "projectId": node.project_id,
                    "spaceId": node.space_id,
                    "branchId": node.branch_id,
                    "parentId": node.id,
                    "rootBranch": node.root_branch,
                    "nodeType": "task",
                    "status": "temporary",
                    "title": str(payload.get("title") or normalize_excerpt(f"Memory proposal for {node.title}", 72)),
                    "content": "\n".join(
                        part
                        for part in [
                            f"Target node: {node.id}",
                            f"Target latest version: {node.latest_version_id}",
                            f"Proposal: {proposal}",
                            f"Rationale: {str(payload.get('rationale') or '').strip()}" if payload.get("rationale") else None,
                        ]
                        if part
                    ),
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                    "createdBy": actor,
                    "updatedBy": actor,
                    "changeReason": "memory-proposal",
                }
            )
            return {
                "status": "proposed",
                "proposalNode": _memory_node_payload(proposal_node),
                "targetNodeId": node.id,
                "targetLatestVersionId": node.latest_version_id,
                "summary": normalize_excerpt(f"Created memory proposal under node {node.title}.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
def forget_memory_node_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    node_id = str(payload.get("nodeId") or "").strip()
    if not node_id:
        raise KeyError("nodeId")

    actor = _memory_tool_actor(execution_context)
    source_work_tree_node_id = _memory_source_work_tree_node_id(execution_context)
    runtime = get_persistence_runtime()

    def _action() -> dict[str, object]:
        with runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            node_repository = NodeRepository(session)
            node = node_repository.get_node(node_id)
            if node is None:
                raise KeyError(f"Node {node_id} not found.")
            version = node_repository.append_version(
                node_id,
                {
                    "status": str(payload.get("status") or "archived"),
                    "mergedIntoNodeId": str(payload.get("mergedIntoNodeId")) if payload.get("mergedIntoNodeId") is not None else None,
                    "changeReason": str(payload.get("reason") or "forget-memory-node"),
                    "createdBy": actor,
                    "updatedBy": actor,
                    "sourceWorkTreeNodeId": source_work_tree_node_id,
                },
            )
            updated_node = node_repository.get_node(node_id)
            return {
                "status": "forgotten",
                "node": _memory_node_payload(updated_node) if updated_node is not None else None,
                "version": _memory_version_payload(version),
                "summary": normalize_excerpt(f"Soft-forgot memory node {node.title}.", 160),
            }

    return _run_with_sqlite_lock_retry(_action)
plugin = TextMemoryModule()
def retrieve_memory_tool(payload: dict[str, object]) -> dict[str, object]:
    execution_context = payload.get("executionContext") if isinstance(payload.get("executionContext"), dict) else {}
    branch_id = str(payload.get("branchId") or execution_context.get("branchId") or DEFAULT_BRANCH_ID)
    query_text = str(payload.get("queryText") or "").strip()
    if not query_text:
        raise KeyError("queryText")
    active_capabilities = [
        str(module_id)
        for module_id in execution_context.get("activeCapabilities") or []
        if str(module_id) != plugin.module_id
    ]

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        node_repository = NodeRepository(session)
        nodes = [
            node.model_dump(by_alias=True, mode="json")
            for node in node_repository.list_nodes(branch_id=branch_id, limit=int(payload.get("nodeScanLimit") or 200))
            if node.node_type != "root"
        ]
        edges = [
            edge.model_dump(by_alias=True, mode="json")
            for edge in node_repository.list_edges(branch_id=branch_id, limit=int(payload.get("edgeScanLimit") or 200))
        ]
        source_annotations = [
            annotation.model_dump(by_alias=True, mode="json")
            for annotation in node_repository.list_source_annotations(branch_id=branch_id, limit=int(payload.get("annotationLimit") or 200))
        ]

    retrieval_request = {
        "id": new_id("retr", branch_id, query_text),
        "queryText": query_text,
        "maxLeafNodes": int(payload.get("maxLeafNodes") or 4),
        "maxRelatedNodes": int(payload.get("maxRelatedNodes") or 4),
        "tokenBudget": int(payload["tokenBudget"]) if payload.get("tokenBudget") is not None else None,
    }
    retrieval_payload = {
        "retrievalRequest": retrieval_request,
        "nodes": nodes,
        "edges": edges,
        "sourceAnnotations": source_annotations,
        "executionContext": execution_context,
    }

    if active_capabilities:
        expansion_results = collect_hook_results(
            HookNames.MEMORY_RETRIEVE_EXPAND,
            retrieval_payload,
            module_ids=active_capabilities,
        )
        nodes_by_id = {str(node.get("id")): node for node in nodes if node.get("id") is not None}
        edges_by_id = {str(edge.get("id")): edge for edge in edges if edge.get("id") is not None}
        annotations_by_id = {
            str(annotation.get("id")): annotation
            for annotation in source_annotations
            if annotation.get("id") is not None
        }
        module_expansions: list[dict[str, object]] = []
        for item in expansion_results:
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            module_expansions.append(
                {
                    "moduleId": item.get("moduleId"),
                    "summary": result.get("summary"),
                }
            )
            for node in result.get("nodes") or []:
                if isinstance(node, dict) and node.get("id") is not None:
                    nodes_by_id[str(node["id"])] = node
            for edge in result.get("edges") or []:
                if isinstance(edge, dict) and edge.get("id") is not None:
                    edges_by_id[str(edge["id"])] = edge
            for annotation in result.get("sourceAnnotations") or []:
                if isinstance(annotation, dict) and annotation.get("id") is not None:
                    annotations_by_id[str(annotation["id"])] = annotation
        retrieval_payload["nodes"] = list(nodes_by_id.values())
        retrieval_payload["edges"] = list(edges_by_id.values())
        retrieval_payload["sourceAnnotations"] = list(annotations_by_id.values())
        retrieval_payload["moduleExpansions"] = module_expansions

    retrieval_bundle = plugin.expand_retrieval(retrieval_payload)
    if active_capabilities:
        rerank_results = collect_hook_results(
            HookNames.MEMORY_RETRIEVE_RERANK,
            {
                **retrieval_payload,
                "retrievalBundle": retrieval_bundle,
            },
            module_ids=active_capabilities,
        )
        for item in rerank_results:
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            if isinstance(result.get("matchedNodeRefs"), list):
                retrieval_bundle["matchedNodeRefs"] = [reference for reference in result["matchedNodeRefs"] if isinstance(reference, dict)]
            if isinstance(result.get("nodePayloads"), list):
                retrieval_bundle["nodePayloads"] = [node for node in result["nodePayloads"] if isinstance(node, dict)]
            if result.get("naturalLanguageSummary"):
                retrieval_bundle["naturalLanguageSummary"] = str(result["naturalLanguageSummary"])
            if isinstance(result.get("relatedNameMap"), dict):
                retrieval_bundle["relatedNameMap"] = dict(result["relatedNameMap"])
    return retrieval_bundle