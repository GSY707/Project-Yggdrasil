from __future__ import annotations

from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule
from yggdrasil_relation_discovery.plugin import RelationDiscoveryModule
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import AssetRepository, NodeRepository, WorkspaceBootstrapRepository


def _context_parent_id(repository: NodeRepository, branch_id: str = DEFAULT_BRANCH_ID) -> str:
    _, context_refs, _ = repository.root_mount_refs(DEFAULT_PROJECT_ID, branch_id)
    return context_refs[0].id


def _create_context_node(
    repository: NodeRepository,
    *,
    title: str,
    content: str,
    branch_id: str = DEFAULT_BRANCH_ID,
    space_id: str = DEFAULT_SPACE_ID,
) -> str:
    node = repository.create_node(
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": space_id,
            "branchId": branch_id,
            "parentId": _context_parent_id(repository, branch_id),
            "rootBranch": "context",
            "nodeType": "detail",
            "title": title,
            "content": content,
            "createdBy": {"type": "user", "id": "pytest"},
            "updatedBy": {"type": "user", "id": "pytest"},
        }
    )
    return node.id


def test_multimodal_ingest_and_relation_discovery_materialize_assets_and_edges() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        nodes = NodeRepository(session)
        owner_node_id = _context_parent_id(nodes)
        related_node_id = _create_context_node(
            nodes,
            title="Runtime Graph Notes",
            content="multimodal memory shared-space training-lab runtime recovery knowledge graph",
        )

    ingest_result = MultimodalMemoryModule().ingest_asset(
        {
            "mediaType": "audio",
            "sourceText": "multimodal memory shared-space training-lab runtime recovery knowledge graph transcript",
            "ownerNodeId": owner_node_id,
            "executionContext": {"sourceWorkTreeNodeId": "wt-node-multimodal"},
        }
    )
    assert ingest_result["segmentCount"] >= 1

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        assets = AssetRepository(session)
        nodes = NodeRepository(session)
        asset = assets.get_asset(ingest_result["asset"]["id"])
        segments = assets.list_asset_segments(ingest_result["asset"]["id"])
        summary_node = nodes.get_node(ingest_result["summaryNode"]["id"])
        assert asset is not None
        assert asset.media_type == "audio"
        assert asset.related_work_tree_node_ids == ["wt-node-multimodal"]
        assert segments
        assert all(segment.embedding_id for segment in segments)
        assert summary_node is not None
        assert summary_node.source_work_tree_node_id == "wt-node-multimodal"

    relation_module = RelationDiscoveryModule()
    scan_result = relation_module.scan_branch_relations({"branchId": DEFAULT_BRANCH_ID})
    assert any(
        {edge["fromNodeId"], edge["toNodeId"]} == {related_node_id, ingest_result["summaryNode"]["id"]}
        for edge in scan_result["createdEdges"]
    )
    assert any(
        {edge["fromNodeId"], edge["toNodeId"]} == {related_node_id, ingest_result["summaryNode"]["id"]}
        and "source-work-tree:wt-node-multimodal" in str(edge.get("reason") or "")
        for edge in scan_result["createdEdges"]
    )

    reranked = relation_module.rerank_retrieval(
        {
            "edges": scan_result["createdEdges"],
            "retrievalBundle": {
                "nodePayloads": [
                    {
                        "ref": {"kind": "node", "id": ingest_result["summaryNode"]["id"]},
                        "title": ingest_result["summaryNode"]["title"],
                        "relatedNames": ["multimodal", "runtime"],
                    },
                    {
                        "ref": {"kind": "node", "id": related_node_id},
                        "title": "Runtime Graph Notes",
                        "relatedNames": ["shared-space", "graph", "recovery"],
                    },
                ]
            },
        }
    )
    assert reranked["matchedNodeRefs"]
    assert "Top linked nodes" in reranked["naturalLanguageSummary"]