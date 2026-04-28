from __future__ import annotations

import json
from pathlib import Path

from yggdrasil_agent_runtime.runtime import build_root_mount_package, prepare_pause_snapshot
from yggdrasil_memory_organizer.plugin import MemoryOrganizerModule
from yggdrasil_multimodal_memory.plugin import MultimodalMemoryModule
from yggdrasil_pause_resume.plugin import PauseResumeModule
from yggdrasil_relation_discovery.plugin import RelationDiscoveryModule
from yggdrasil_shared_memory.plugin import SharedMemoryModule
from yggdrasil_training_lab.plugin import TrainingLabModule
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID, DEFAULT_SPACE_ID
from yggdrasil_sdk.persistence.repositories import (
    AssetRepository,
    CollaborationRepository,
    NodeRepository,
    PromptAssetRepository,
    RuntimeRepository,
    TrainingRepository,
    WorkspaceBootstrapRepository,
)
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.support import ensure_state_subdir, relative_workspace_path, resolve_workspace_root, write_json


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


def _resolve_locator_path(locator: str) -> Path:
    path = Path(locator)
    if path.is_absolute():
        return path
    return resolve_workspace_root() / locator


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


def test_pause_resume_module_adds_resume_digest_and_rehydrates_context() -> None:
    snapshot = prepare_pause_snapshot(
        "task_pause_m9",
        {
            "agentRunId": "run_pause_m9",
            "pendingActions": [{"kind": "await-human-review"}],
            "currentResponseState": "completed",
            "currentContextState": [
                {
                    "id": "ctx_restore",
                    "title": "Resume Context",
                    "content": "resume recovery shared memory runtime graph",
                }
            ],
        },
    )
    assert snapshot["safeToPause"] is True
    assert any(action["kind"] == "resume-digest" for action in snapshot["pendingActions"])
    assert any("Prepared safe-stop" in summary for summary in snapshot["moduleSummaries"])

    rehydrated = PauseResumeModule().rehydrate_resume(
        {
            "taskSnapshot": snapshot,
            "rootMounts": snapshot["rootMountPreview"],
        }
    )
    assert rehydrated["restoredState"]["currentContext"][0]["id"] == "ctx_restore"
    assert rehydrated["followupActions"][0]["kind"] == "resume-checkpoint"


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
        }
    )
    assert ingest_result["segmentCount"] >= 1

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        assets = AssetRepository(session)
        asset = assets.get_asset(ingest_result["asset"]["id"])
        segments = assets.list_asset_segments(ingest_result["asset"]["id"])
        assert asset is not None
        assert asset.media_type == "audio"
        assert segments
        assert all(segment.embedding_id for segment in segments)

    relation_module = RelationDiscoveryModule()
    scan_result = relation_module.scan_branch_relations({"branchId": DEFAULT_BRANCH_ID})
    assert any(
        {edge["fromNodeId"], edge["toNodeId"]} == {related_node_id, ingest_result["summaryNode"]["id"]}
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


def test_training_lab_creates_dataset_and_validated_model_artifact() -> None:
    workspace_root = resolve_workspace_root()
    state_dir = ensure_state_subdir("training-lab-fixtures", workspace_root)
    compiled_messages_path = state_dir / "compiled-messages.json"
    request_path = state_dir / "request.json"
    response_path = state_dir / "response.json"
    write_json(compiled_messages_path, {"messages": [{"role": "user", "content": "design a recovery plan"}]})
    write_json(request_path, {"input": "design a recovery plan"})
    write_json(response_path, {"rawResponse": {"text": "deliver a staged runtime recovery plan"}})

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_assets = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        artifact = prompt_assets.create_prompt_compile_artifact(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "promptProfileVersionId": "profile_v1",
                "runType": "main",
                "taskType": "planning",
                "registeredTools": [
                    {"name": "shared_memory.describe_mounts"},
                    {"name": "training_lab.prepare_dataset"},
                ],
                "compiledMessagesRef": {
                    "type": "file",
                    "locator": relative_workspace_path(compiled_messages_path, workspace_root),
                },
                "contentHash": "content_hash_training_lab",
            }
        )
        assert artifact.app_id == DEFAULT_APP_ID
        invocation = runtime_repository.create_model_invocation(
            {
                "projectId": DEFAULT_PROJECT_ID,
                "requestedModel": "gpt-4.1-mini",
                "requestedProvider": "copilot",
                "resolvedModel": "gpt-4.1-mini",
                "resolvedProvider": "copilot",
                "status": "completed",
                "promptCompileArtifactId": artifact.id,
                "requestRef": {
                    "type": "file",
                    "locator": relative_workspace_path(request_path, workspace_root),
                },
                "responseRef": {
                    "type": "file",
                    "locator": relative_workspace_path(response_path, workspace_root),
                },
                "inputTokensUsed": 32,
                "outputTokensUsed": 48,
                "costUsed": 0.02,
            }
        )
        assert invocation.app_id == DEFAULT_APP_ID

    training_lab = TrainingLabModule()
    dataset_result = training_lab.prepare_dataset(
        {
            "datasetName": "m9_training_lab",
            "branchId": DEFAULT_BRANCH_ID,
            "maxRows": 6,
            "includeMemoryNodes": False,
        }
    )
    assert dataset_result["datasetVersion"]["rowCount"] >= 1
    assert dataset_result["previewRows"][0]["kind"] == "prompt-artifact"
    dataset_path = _resolve_locator_path(dataset_result["datasetVersion"]["storageKey"])
    assert dataset_path.exists()
    assert json.loads(dataset_path.read_text(encoding="utf-8").splitlines()[0])["kind"] == "prompt-artifact"

    model_result = training_lab.stage_model_artifact(
        {
            "datasetVersionId": dataset_result["datasetVersion"]["id"],
            "baseModel": "gpt-4.1-mini",
            "tuningMethod": "distillation",
            "minimumRows": 1,
        }
    )
    assert model_result["modelArtifact"]["status"] == "validated"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        training_repository = TrainingRepository(session)
        dataset = training_repository.get_dataset_version(dataset_result["datasetVersion"]["id"])
        artifacts = training_repository.list_model_artifacts(limit=20)
        assert dataset is not None
        assert any(artifact.id == model_result["modelArtifact"]["id"] for artifact in artifacts)