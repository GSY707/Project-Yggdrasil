from __future__ import annotations

from yggdrasil_agent_runtime.runtime import build_root_mount_package
from yggdrasil_shared_memory.plugin import SharedMemoryModule
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import CollaborationRepository, NodeRepository, WorkspaceBootstrapRepository


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


def test_shared_memory_mounts_expand_retrieval_and_redirect_copy_on_write() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration = CollaborationRepository(session)
        nodes = NodeRepository(session)
        mounted_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:architect",
            }
        )
        mounted_branch = collaboration.create_branch(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": mounted_space.id,
                "name": "shared-runtime-space",
            }
        )
        _create_context_node(
            nodes,
            title="Shared Runtime Guide",
            content="shared-space runtime recovery multimodal memory graph",
            branch_id=mounted_branch.id,
            space_id=mounted_space.id,
        )
        collaboration.create_space_mount(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "hostSpaceId": DEFAULT_SPACE_ID,
                "mountedSpaceId": mounted_space.id,
                "mountMode": "copy-on-write",
            }
        )
        collaboration.create_permission_tuple(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "subject": "profile:architect",
                "relation": "mount",
                "resource": f"space:{mounted_space.id}",
            }
        )

    mount_package = build_root_mount_package(
        "task_shared_m9",
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": DEFAULT_SPACE_ID,
            "branchId": DEFAULT_BRANCH_ID,
            "subject": "profile:architect",
            "activeCapabilities": ["shared-memory"],
        },
    )
    assert any(mount["mountedSpaceId"] == mounted_space.id for mount in mount_package["accessibleMounts"])
    assert any(fragment["moduleId"] == "shared-memory" for fragment in mount_package["moduleMountFragments"])

    shared_memory = SharedMemoryModule()
    expanded = shared_memory.expand_retrieval(
        {
            "executionContext": {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": DEFAULT_SPACE_ID,
                "branchId": DEFAULT_BRANCH_ID,
                "subject": "profile:architect",
                "rootMount": {"spaceId": DEFAULT_SPACE_ID},
            }
        }
    )
    assert any(node["mountedSpaceId"] == mounted_space.id for node in expanded["nodes"])

    validation = shared_memory.validate_memory_write(
        {
            "projectId": DEFAULT_PROJECT_ID,
            "subject": "profile:architect",
            "hostSpaceId": DEFAULT_SPACE_ID,
            "spaceId": DEFAULT_SPACE_ID,
            "branchId": DEFAULT_BRANCH_ID,
            "targetSpaceId": mounted_space.id,
            "targetBranchId": mounted_branch.id,
        }
    )
    assert validation["allowed"] is True
    assert validation["targetSpaceId"] == DEFAULT_SPACE_ID
    assert "Copy-on-write" in validation["summary"]