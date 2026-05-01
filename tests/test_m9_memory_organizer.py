from __future__ import annotations

from yggdrasil_memory_organizer.plugin import MemoryOrganizerModule
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import NodeRepository, WorkspaceBootstrapRepository


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


def test_memory_organizer_soft_forgetting_updates_low_value_nodes() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        nodes = NodeRepository(session)
        low_node_id = _create_context_node(
            nodes,
            title="Discardable Scratchpad",
            content="temporary note for cleanup and compression",
        )
        node = nodes.get_node(low_node_id)
        assert node is not None
        nodes.append_version(
            low_node_id,
            {
                "importance": 0.1,
                "stability": 0.2,
                "accessScore": 0.0,
                "feedforwardScore": 0.0,
                "changeReason": "prepare-soft-forgetting-test",
                "updatedBy": {"type": "user", "id": "pytest"},
            },
        )
        _create_context_node(
            nodes,
            title="Critical Architecture Note",
            content="persistent high-value architecture memory for runtime recovery and governance",
        )

    organizer = MemoryOrganizerModule()
    preview = organizer.apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": True,
        }
    )
    assert preview["status"] == "preview"
    assert preview["candidates"][0]["nodeId"] == low_node_id

    applied = organizer.apply_soft_forgetting(
        {
            "branchId": DEFAULT_BRANCH_ID,
            "targetCount": 1,
            "dryRun": False,
        }
    )
    assert applied["adjustedNodes"][0]["nodeId"] == low_node_id

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        nodes = NodeRepository(session)
        updated = nodes.get_node(low_node_id)
        assert updated is not None
        assert updated.latest_version_id is not None
        assert updated.forget_rate >= 0.35
        assert len(updated.content) <= len("temporary note for cleanup and compression")