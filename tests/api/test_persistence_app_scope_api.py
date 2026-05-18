from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from yggdrasil_core_api.app import app
from yggdrasil_sdk import (
    PromptAssetRepository,
    PromptProfileVersionRecord,
    SeedTemplateVersionRecord,
    TaskRepository,
    TaskSnapshotSummary,
    get_persistence_runtime,
    new_id,
    run_evaluation_suite,
    utc_now,
)
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.repositories import RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, relative_workspace_path, resolve_workspace_root, write_json


def _seed_prompt_profile_version(prompt_repository: PromptAssetRepository, *, version_id: str, prompt_profile_id: str) -> None:
    prompt_repository.upsert_prompt_profile_version(
        PromptProfileVersionRecord(
            id=version_id,
            promptProfileId=prompt_profile_id,
            name=prompt_profile_id,
            version="v1",
            runScope="any",
            body={"id": prompt_profile_id, "version": "v1"},
            contentHash=f"{version_id}-hash",
            createdAt=utc_now(),
        )
    )


def _seed_seed_template_version(prompt_repository: PromptAssetRepository, *, version_id: str, seed_template_id: str) -> None:
    prompt_repository.upsert_seed_template_version(
        SeedTemplateVersionRecord(
            id=version_id,
            seedTemplateId=seed_template_id,
            name=seed_template_id,
            version="v1",
            domain="generic",
            scenario="control-plane",
            body={"id": seed_template_id, "version": "v1", "domain": "generic", "scenario": "control-plane"},
            contentHash=f"{version_id}-hash",
            createdAt=utc_now(),
        )
    )


client = TestClient(app)
pytestmark = pytest.mark.slow

def test_core_api_filters_app_scoped_records() -> None:
    app_id = "yggdrasil.app.demo"
    workspace_root = resolve_workspace_root()
    prompt_dir = ensure_state_subdir("tests/app-scope", workspace_root)
    compiled_messages_path = prompt_dir / "compiled.json"
    write_json(compiled_messages_path, {"messages": [{"role": "user", "content": "列出当前应用域的运行记录。"}]})

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        _seed_prompt_profile_version(
            prompt_repository,
            version_id="prompt_profile_app_scope",
            prompt_profile_id="yggdrasil.app-scope.fixture",
        )
        task = task_repository.create_task(
            {
                "id": "task_api_app_scope",
                "appId": app_id,
                "title": "应用域过滤测试",
                "goal": "验证 tasks/runtime/prompting 均可按 appId 过滤。",
            }
        )
        run = task_repository.create_agent_run(
            task.id,
            {
                "id": "run_api_app_scope",
                "status": "completed",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        artifact = prompt_repository.create_prompt_compile_artifact(
            {
                "id": "artifact_api_app_scope",
                "projectId": task.project_id,
                "taskId": task.id,
                "agentRunId": run.id,
                "promptProfileVersionId": "prompt_profile_app_scope",
                "runType": "main",
                "taskType": "analysis",
                "registeredTools": [{"name": "text_memory.search"}],
                "compiledMessagesRef": {
                    "type": "file",
                    "locator": relative_workspace_path(compiled_messages_path, workspace_root),
                },
                "contentHash": "app-scope-hash",
            }
        )
        invocation = runtime_repository.create_model_invocation(
            {
                "id": "llm_api_app_scope",
                "projectId": task.project_id,
                "taskId": task.id,
                "agentRunId": run.id,
                "promptCompileArtifactId": artifact.id,
                "requestedModel": "gpt-5.4",
                "requestedProvider": "copilot",
                "resolvedModel": "gpt-5.4",
                "resolvedProvider": "copilot",
                "status": "completed",
                "inputTokensUsed": 12,
                "outputTokensUsed": 18,
                "costUsed": 0.002,
            }
        )

    tasks_response = client.get("/tasks", params={"appId": app_id})
    assert tasks_response.status_code == 200
    tasks = tasks_response.json()["tasks"]
    assert any(task["id"] == "task_api_app_scope" for task in tasks)
    assert all(task["appId"] == app_id for task in tasks)

    invocations_response = client.get("/runtime/model-invocations", params={"appId": app_id})
    assert invocations_response.status_code == 200
    invocations = invocations_response.json()["modelInvocations"]
    assert any(item["id"] == invocation.id for item in invocations)
    assert all(item["appId"] == app_id for item in invocations)

    artifacts_response = client.get("/prompting/compile-artifacts", params={"appId": app_id})
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()["promptCompileArtifacts"]
    assert any(item["id"] == artifact.id for item in artifacts)
    assert all(item["appId"] == app_id for item in artifacts)


def test_evaluation_suite_covers_m9_control_plane() -> None:
    result = run_evaluation_suite("evalsuite_regression_m9_control_plane")
    metrics = result["metrics"]
    assert metrics["status"] == "completed"
    assert metrics["failedCount"] == 0
    assert metrics["passedCount"] == 2
