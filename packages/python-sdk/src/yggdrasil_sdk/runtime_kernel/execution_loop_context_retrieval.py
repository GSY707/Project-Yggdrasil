from __future__ import annotations

from .execution_loop_metrics_memory_tags import *  # noqa: F403,F401

def _retrieve_context_from_memory_tree(
    session,
    *,
    task,
    request: dict[str, Any],
    root_mount: dict[str, Any],
    current_context: list[dict[str, Any]],
    execution_root_id: str,
) -> dict[str, Any]:
    runtime_metrics = request.get("runtimeMetrics") if isinstance(request.get("runtimeMetrics"), dict) else {}
    window_index = max(_int_metric(runtime_metrics.get("windowIndex"), _int_metric(request.get("windowIndex"), 1)), 1)
    work_tree_node_id = _work_tree_node_id_from_request(request)
    materialized_node_ids = _materialize_runtime_context_items(
        session,
        task=task,
        current_context=current_context,
        root_mount=root_mount,
        execution_root_id=execution_root_id,
        window_index=window_index,
        source_work_tree_node_id=work_tree_node_id,
        source_run_id=(
            str(request.get("agentRunId") or "").strip()
            or str(request.get("parentRunId") or "").strip()
            or None
        ),
    )

    repository = NodeRepository(session)
    memory_repository = MemoryRepository(session)
    nodes = [
        node.model_dump(by_alias=True, mode="json")
        for node in repository.list_nodes(branch_id=task.branch_id, limit=2000)
        if node.node_type != "root"
    ]
    edges = [edge.model_dump(by_alias=True, mode="json") for edge in repository.list_edges(branch_id=task.branch_id, limit=4000)]
    annotations = [
        annotation.model_dump(by_alias=True, mode="json")
        for annotation in repository.list_source_annotations(branch_id=task.branch_id, limit=4000)
    ]

    active_capabilities = [str(item) for item in root_mount.get("activeCapabilities") or []]
    execution_context = {
        "projectId": task.project_id,
        "spaceId": task.space_id,
        "branchId": task.branch_id,
        "ownerProfileId": task.owner_profile_id,
        "subject": request.get("subject") or (f"profile:{task.owner_profile_id}" if task.owner_profile_id else None),
        "rootMount": root_mount,
    }
    expansion_summaries: list[str] = []
    expansion_module_ids = [module_id for module_id in active_capabilities if module_id != "text-memory"] or None
    if expansion_module_ids:
        for item in collect_hook_results(
            HookNames.MEMORY_RETRIEVE_EXPAND,
            {
                "projectId": task.project_id,
                "spaceId": task.space_id,
                "branchId": task.branch_id,
                "ownerProfileId": task.owner_profile_id,
                "subject": execution_context["subject"],
                "executionContext": execution_context,
            },
            module_ids=expansion_module_ids,
        ):
            if item.get("error"):
                continue
            result = item.get("result") if isinstance(item.get("result"), dict) else {}
            nodes.extend(node for node in result.get("nodes") or [] if isinstance(node, dict))
            edges.extend(edge for edge in result.get("edges") or [] if isinstance(edge, dict))
            annotations.extend(annotation for annotation in result.get("sourceAnnotations") or [] if isinstance(annotation, dict))
            if result.get("summary") is not None:
                expansion_summaries.append(str(result["summary"]))

    retrieval_query = " ".join(
        part.strip()
        for part in [
            str(request.get("taskObjective") or request.get("currentObjective") or task.current_objective or task.goal or ""),
            str(request.get("currentFocus") or task.current_focus or ""),
            str(request.get("resumeMessage") or root_mount.get("resumeMessage") or ""),
        ]
        if part and part.strip()
    )
    retrieval_request = {
        "id": new_id("retr", task.id, utc_now().isoformat()),
        "projectId": task.project_id,
        "spaceId": task.space_id,
        "branchId": task.branch_id,
        "queryText": retrieval_query,
        "seedNodeRefs": [
            *[dict(reference) for reference in root_mount.get("identityRefs") or [] if isinstance(reference, dict)],
            *[dict(reference) for reference in root_mount.get("contextRefs") or [] if isinstance(reference, dict)],
            *[dict(reference) for reference in root_mount.get("executionRefs") or [] if isinstance(reference, dict)],
            *[{"kind": "node", "id": node_id} for node_id in materialized_node_ids],
        ],
        "traversalStart": "mixed",
        "expansionMode": "parallel",
        "readDepth": 2,
        "lateralHops": 1,
        "maxRelatedNodes": 6,
        "maxLeafNodes": 6,
        "precisionMode": "balanced",
        "includeNaturalLanguageSummary": True,
        "includeChildNames": True,
        "includeRelatedNames": True,
        "reverseTraceMode": bool(request.get("memoryReverseTraceMode", work_tree_node_id is not None)),
        "workTreeNodeId": work_tree_node_id,
        "windowIndex": window_index,
        "tokenBudget": request.get("maxRetainedTokens"),
        "createdAt": utc_now().isoformat(),
    }
    retrieval_request_record = memory_repository.create_retrieval_request(retrieval_request)
    retrieval_request = retrieval_request_record.model_dump(by_alias=True, mode="json")
    retrieval_bundle = call_module_hook(
        "text-memory",
        HookNames.MEMORY_RETRIEVE_EXPAND,
        {
            "retrievalRequest": retrieval_request,
            "nodes": _dedupe_memory_records(nodes),
            "edges": _dedupe_memory_records(edges),
            "sourceAnnotations": _dedupe_memory_records(annotations),
            "executionContext": execution_context,
        },
    )
    if retrieval_bundle is None:
        return {
            "contextItems": current_context,
            "protectedItems": [],
            "summary": None,
            "materializedNodeIds": materialized_node_ids,
            "retrievalRequest": retrieval_request,
        }

    node_payloads = [item for item in retrieval_bundle.get("nodePayloads") or [] if isinstance(item, dict)]
    matched_refs = [item for item in retrieval_bundle.get("matchedNodeRefs") or [] if isinstance(item, dict)]
    context_items: list[dict[str, Any]] = []
    summary_parts = [str(retrieval_bundle.get("naturalLanguageSummary") or "").strip(), *[summary.strip() for summary in expansion_summaries if summary.strip()]]
    if materialized_node_ids:
        summary_parts.append(f"Materialized {len(materialized_node_ids)} runtime context items into the memory tree before retrieval.")
    summary_text = " ".join(part for part in summary_parts if part)
    if summary_text:
        context_items.append(
            {
                "id": new_id("retrieval-summary", task.id, retrieval_request["id"], stable=True),
                "kind": "retrieval-summary",
                "title": "Memory retrieval summary",
                "content": normalize_excerpt(summary_text, 480),
                "rootBranch": "context",
            }
        )
    context_items.extend(_context_item_from_retrieved_node(item) for item in node_payloads)
    if _should_trim_retrieved_context(current_context):
        context_items = _trim_context_items_to_token_budget(context_items, _memory_retrieval_token_budget(request))
    retained_node_ids = {
        str((item.get("ref") or {}).get("id") or "")
        for item in context_items
        if isinstance(item, dict) and isinstance(item.get("ref"), dict) and item.get("ref", {}).get("id")
    }
    if retained_node_ids:
        matched_refs = [reference for reference in matched_refs if str(reference.get("id") or "") in retained_node_ids]
    else:
        matched_refs = []
    return {
        "contextItems": context_items or current_context,
        "protectedItems": matched_refs,
        "summary": summary_text or None,
        "materializedNodeIds": materialized_node_ids,
        "retrievalRequest": retrieval_request,
        "retrievalBundle": retrieval_bundle,
    }
