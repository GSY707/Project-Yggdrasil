from __future__ import annotations

import json
from pathlib import Path

from yggdrasil_training_lab.plugin import TrainingLabModule
from yggdrasil_sdk import PromptProfileVersionRecord, utc_now
from yggdrasil_sdk.persistence import get_persistence_runtime
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID, DEFAULT_BRANCH_ID, DEFAULT_PROJECT_ID
from yggdrasil_sdk.persistence.repositories import (
    PromptAssetRepository,
    RuntimeRepository,
    TrainingRepository,
    WorkspaceBootstrapRepository,
)
from yggdrasil_sdk.support import ensure_state_subdir, relative_workspace_path, resolve_workspace_root, write_json


def _resolve_locator_path(locator: str) -> Path:
    path = Path(locator)
    if path.is_absolute():
        return path
    return resolve_workspace_root() / locator


def _seed_training_lab_prompt_profile(prompt_assets: PromptAssetRepository) -> None:
    prompt_assets.upsert_prompt_profile_version(
        PromptProfileVersionRecord(
            id="profile_v1",
            promptProfileId="yggdrasil.training-lab.fixture",
            name="Training Lab Fixture",
            version="v1",
            runScope="any",
            body={"id": "yggdrasil.training-lab.fixture", "version": "v1"},
            contentHash="training-lab-profile-v1",
            createdAt=utc_now(),
        )
    )


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
        _seed_training_lab_prompt_profile(prompt_assets)
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