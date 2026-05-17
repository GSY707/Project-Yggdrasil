from __future__ import annotations

import pytest

from yggdrasil_agent_runtime.runtime import build_root_mount_package
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_PROJECT_ID
from yggdrasil_sdk.persistence.repositories import CollaborationRepository, WorkspaceBootstrapRepository
from yggdrasil_task_takeover.plugin import TaskTakeoverModule


def test_create_task_bootstraps_missing_branch_workspace_for_existing_space() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration = CollaborationRepository(session)
        task_repository = TaskRepository(session)
        mounted_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4",
            }
        )
        task = task_repository.create_task(
            {
                "id": "task_p4_bootstrap",
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": mounted_space.id,
                "branchId": "branch_p4_bootstrap",
                "branchName": "p4-bootstrap",
                "title": "bootstrap task",
                "goal": "ensure workspace is initialized",
            }
        )

    mount_package = build_root_mount_package(task.id)

    assert task.branch_id == "branch_p4_bootstrap"
    assert mount_package["branchId"] == "branch_p4_bootstrap"
    assert mount_package["source"] == "database"
    assert mount_package["executionRefs"][0]["id"] == task.execution_root_node_id


def test_create_task_rejects_branch_space_mismatch() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        collaboration = CollaborationRepository(session)
        task_repository = TaskRepository(session)
        first_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4-a",
            }
        )
        second_space = collaboration.create_space(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceType": "shared",
                "ownerSubject": "profile:p4-b",
            }
        )
        branch = collaboration.create_branch(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "spaceId": first_space.id,
                "name": "branch-p4-mismatch",
            }
        )

        with pytest.raises(ValueError, match="does not belong to space"):
            task_repository.create_task(
                {
                    "id": "task_p4_mismatch",
                    "projectId": DEFAULT_PROJECT_ID,
                    "spaceId": second_space.id,
                    "branchId": branch.id,
                    "title": "invalid task",
                    "goal": "should fail",
                }
            )


def test_root_mount_exposes_root_branches_and_startup_contract() -> None:
    mount_package = build_root_mount_package(
        "task_p4_contract",
        {
            "projectId": DEFAULT_PROJECT_ID,
            "spaceId": "space_p4_preview",
            "branchId": "branch_p4_preview",
            "taskObjective": "stabilize startup contract",
            "responseRequirements": "必须包含 result/evidence/pending/incomplete。",
            "restartMessage": "窗口切换后沿当前节点继续。",
        },
    )

    assert mount_package["rootBranches"] == {
        "identity": mount_package["identityRefs"][0]["id"],
        "context": mount_package["contextRefs"][0]["id"],
        "execution": mount_package["executionRefs"][0]["id"],
    }
    assert mount_package["startupContract"]["responseRequirements"] == "必须包含 result/evidence/pending/incomplete。"
    assert mount_package["startupContract"]["restartMessage"] == "窗口切换后沿当前节点继续。"


def test_task_takeover_extracts_root_mount_and_startup_contract_constraints() -> None:
    result = TaskTakeoverModule().extract_constraints(
        {
            "request": {},
            "rootMount": {
                "budgetState": {},
                "activeCapabilities": ["task-takeover"],
                "rootBranches": {
                    "identity": "node_identity",
                    "context": "node_context",
                    "execution": "node_execution",
                },
                "startupContract": {
                    "responseRequirements": "必须先给正式交付。",
                    "restartMessage": "按当前 work tree 节点恢复。",
                },
            },
        }
    )

    labels = {item["label"]: item for item in result["constraints"]}
    assert labels["根挂载"]["source"] == "root-mount"
    assert labels["启动合同"]["value"] == "必须先给正式交付。"
    assert labels["重启交接"]["value"] == "按当前 work tree 节点恢复。"


def test_work_tree_bootstraps_pointer_when_plan_is_empty() -> None:
    protocol = runtime_takeover._work_tree_from_protocol_parts(
        task_id="task_p4_work_tree",
        objective="stabilize takeover bootstrap",
        constraints=[],
        plan=[],
        protocol_status="prepared",
    )

    assert protocol.current_node_id is not None
    assert protocol.nodes[0].title == "Establish executable plan"
    assert protocol.nodes[0].recovery_anchor == "resume:bootstrap"