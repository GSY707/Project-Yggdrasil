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


def test_core_api_persists_task_and_node_records() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api",
            "title": "通过 API 创建正式任务",
            "goal": "验证 core-api 已切到正式持久化层。",
            "status": "queued",
        },
    )
    assert created_task.status_code == 201
    assert created_task.json()["task"]["id"] == "task_api"
    assert created_task.json()["task"]["appId"] == DEFAULT_APP_ID

    created_node = client.post(
        "/nodes",
        json={
            "id": "node_api",
            "title": "API 节点",
            "content": "这个节点通过 core-api 落到持久化底座。",
            "nodeType": "detail",
            "rootBranch": "execution",
        },
    )
    assert created_node.status_code == 201
    assert created_node.json()["node"]["id"] == "node_api"

    fetched_task = client.get("/tasks/task_api")
    assert fetched_task.status_code == 200
    assert fetched_task.json()["task"]["status"] == "queued"
    assert fetched_task.json()["task"]["appId"] == DEFAULT_APP_ID

    fetched_node = client.get("/nodes/node_api")
    assert fetched_node.status_code == 200
    assert fetched_node.json()["node"]["title"] == "API 节点"


def test_core_api_exposes_route_decisions_and_outbox() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api_2",
            "title": "路由决策任务",
            "goal": "为 route decision 提供正式 task 上下文。",
        },
    )
    assert created_task.status_code == 201

    decision = client.post(
        "/runtime/route-decisions",
        json={
            "taskId": "task_api_2",
            "selectedModel": "gpt-5.4",
            "selectedProvider": "copilot",
            "candidateModels": ["gpt-5.4", "claude-3.7-sonnet"],
            "reason": "编码任务优先选高质量模型。",
            "budgetScore": 0.6,
            "qualityScore": 0.95,
            "latencyScore": 0.55,
        },
    )
    assert decision.status_code == 201
    assert decision.json()["routeDecision"]["selectedModel"] == "gpt-5.4"

    outbox = client.get("/outbox")
    assert outbox.status_code == 200
    assert outbox.json()["events"]


def test_core_api_exposes_workbench_evaluations_and_observability() -> None:
    suite_response = client.get("/evaluations/suites")
    assert suite_response.status_code == 200
    suites = suite_response.json()["evaluationSuites"]
    assert any(suite["id"] == "evalsuite_regression_m4_m6" for suite in suites)
    assert any(suite["id"] == "evalsuite_benchmark_m8_memory_strategies" for suite in suites)
    assert any(suite["id"] == "evalsuite_live_m8_llm" for suite in suites)
    assert any(suite["id"] == "evalsuite_regression_m9_control_plane" for suite in suites)

    tasks_response = client.get("/tasks")
    assert tasks_response.status_code == 200

    observability_response = client.get("/observability/summary", params={"limit": 10})
    assert observability_response.status_code == 200
    observability = observability_response.json()
    assert observability["health"]["service"] == "core-api"
    assert any(summary["serviceName"] == "core-api" for summary in observability["serviceSummaries"])
    assert "exporters" in observability
    assert "otel" in observability["exporters"]
    assert "langfuse" in observability["exporters"]

    overview_response = client.get("/workbench/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["evaluationSuites"]
    assert "observability" in overview


def test_core_api_exposes_model_invocations_and_llm_summary() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task_repository.create_task(
            {
                "id": "task_api_llm",
                "title": "模型调用 API 测试",
                "goal": "验证 core-api 能暴露 model invocation 记录。",
            }
        )
        run = task_repository.create_agent_run(
            "task_api_llm",
            {
                "id": "run_api_llm",
                "status": "completed",
                "selectedModel": "LongCat-Flash-Lite",
                "selectedProvider": "longcat",
            },
        )
        decision = runtime_repository.create_model_route_decision(
            {
                "taskId": "task_api_llm",
                "agentRunId": run.id,
                "selectedModel": "LongCat-Flash-Lite",
                "selectedProvider": "longcat",
                "candidateModels": [{"model": "LongCat-Flash-Lite", "provider": "longcat"}],
                "reason": "免费优先。",
                "budgetScore": 1.0,
                "qualityScore": 0.78,
                "latencyScore": 0.8,
            }
        )
        runtime_repository.create_model_invocation(
            {
                "id": "llm_api_1",
                "projectId": "project_default",
                "taskId": "task_api_llm",
                "agentRunId": run.id,
                "routeDecisionId": decision.id,
                "requestedModel": "LongCat-Flash-Lite",
                "requestedProvider": "longcat",
                "resolvedModel": "LongCat-Flash-Lite",
                "resolvedProvider": "longcat",
                "status": "completed",
                "inputTokensUsed": 128,
                "outputTokensUsed": 64,
                "costUsed": 0.0,
            }
        )

    task_response = client.get("/tasks/task_api_llm")
    assert task_response.status_code == 200
    assert len(task_response.json()["modelInvocations"]) == 1

    runtime_response = client.get("/runtime/model-invocations", params={"taskId": "task_api_llm"})
    assert runtime_response.status_code == 200
    invocations = runtime_response.json()["modelInvocations"]
    assert len(invocations) == 1
    assert invocations[0]["appId"] == DEFAULT_APP_ID
    assert invocations[0]["resolvedProvider"] == "longcat"

    observability_response = client.get("/observability/summary", params={"limit": 10})
    assert observability_response.status_code == 200
    llm_summary = observability_response.json()["llmSummary"]
    assert llm_summary["totalInvocations"] >= 1
    assert llm_summary["providerCounts"]["longcat"] >= 1

    overview_response = client.get("/workbench/overview")
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["cards"]["modelInvocations"] >= 1
    assert overview["recentModelInvocations"]


def test_core_api_supports_shared_spaces_mounts_and_permission_tuples() -> None:
    created_space = client.post(
        "/collaboration/spaces",
        json={
            "id": "space_shared_design",
            "projectId": "project_default",
            "spaceType": "shared",
            "ownerSubject": "team:design",
        },
    )
    assert created_space.status_code == 201
    assert created_space.json()["space"]["id"] == "space_shared_design"

    created_branch = client.post(
        "/collaboration/branches",
        json={
            "id": "branch_shared_design_main",
            "projectId": "project_default",
            "spaceId": "space_shared_design",
            "name": "design/main",
            "baseBranchId": "branch_main",
        },
    )
    assert created_branch.status_code == 201
    assert created_branch.json()["branch"]["spaceId"] == "space_shared_design"

    created_mount = client.post(
        "/collaboration/space-mounts",
        json={
            "id": "mount_default_to_design",
            "projectId": "project_default",
            "hostSpaceId": "space_default",
            "mountedSpaceId": "space_shared_design",
            "mountMode": "readonly",
            "createdBy": {"type": "user", "id": "architect"},
        },
    )
    assert created_mount.status_code == 201
    assert created_mount.json()["spaceMount"]["mountMode"] == "readonly"

    created_permission = client.post(
        "/collaboration/permission-tuples",
        json={
            "id": "perm_design_read",
            "projectId": "project_default",
            "subject": "team:design",
            "relation": "memory.read",
            "resource": "space:space_shared_design",
            "effect": "allow",
            "condition": {"mountMode": "readonly"},
            "createdBy": {"type": "user", "id": "architect"},
        },
    )
    assert created_permission.status_code == 201
    assert created_permission.json()["permissionTuple"]["subject"] == "team:design"

    spaces_response = client.get("/collaboration/spaces", params={"projectId": "project_default"})
    assert spaces_response.status_code == 200
    assert any(space["id"] == "space_shared_design" for space in spaces_response.json()["spaces"])

    mounts_response = client.get("/collaboration/space-mounts", params={"hostSpaceId": "space_default"})
    assert mounts_response.status_code == 200
    assert any(mount["id"] == "mount_default_to_design" for mount in mounts_response.json()["spaceMounts"])

    permissions_response = client.get("/collaboration/permission-tuples", params={"subject": "team:design"})
    assert permissions_response.status_code == 200
    assert any(item["id"] == "perm_design_read" for item in permissions_response.json()["permissionTuples"])

    overview_response = client.get("/workbench/overview")
    assert overview_response.status_code == 200
    overview_cards = overview_response.json()["cards"]
    assert overview_cards["sharedSpaces"] >= 1
    assert overview_cards["spaceMounts"] >= 1
    assert overview_cards["permissionTuples"] >= 1


def test_core_api_task_detail_exposes_runtime_control_summary() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": "task_api_resume",
                "title": "恢复控制面验证",
                "goal": "暴露正式 resume 控制摘要。",
                "status": "paused",
                "resumeMessage": "从最近一次 safe-stop 恢复。",
            }
        )
        run = task_repository.create_agent_run(
            task.id,
            {
                "id": "run_api_resume",
                "status": "paused",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        snapshot = task_repository.create_snapshot(
            TaskSnapshotSummary(
                id="snapshot_api_resume",
                appId=task.app_id,
                taskId=task.id,
                agentRunId=run.id,
                projectId=task.project_id,
                branchId=task.branch_id,
                snapshotType="pause",
                status="restorable",
                resumeToken=new_id("resume", task.id, run.id, stable=False),
                contextRef={"type": "package-entry", "locator": f"runtime/tasks/{task.id}/snapshots/context"},
                rootMountRef={"type": "package-entry", "locator": f"runtime/tasks/{task.id}/snapshots/root-mount"},
                pendingWrites=[],
                pendingActions=[],
                resumeMessage="继续完成恢复控制面验证。",
                safeStopReason="manual-safe-stop",
                createdAt=utc_now(),
                safeToPause=True,
                blockers=[],
            )
        )
        task_repository.update_task(
            task.id,
            {
                "status": "paused",
                "activeSnapshotId": snapshot.id,
                "pauseRequested": False,
                "lastSafeStopAt": utc_now(),
            },
        )

    task_response = client.get("/tasks/task_api_resume")
    assert task_response.status_code == 200
    runtime_control = task_response.json()["runtimeControl"]
    assert runtime_control["resumeStatus"] == "ready"
    assert runtime_control["canResume"] is True
    assert runtime_control["activeSnapshotId"] == "snapshot_api_resume"
    assert runtime_control["recommendedResumeToken"]
    assert runtime_control["latestRestorableSnapshot"]["safeStopReason"] == "manual-safe-stop"
    assert runtime_control["latestRestorableSnapshot"]["appId"] == DEFAULT_APP_ID


def test_core_api_exposes_task_control_actions() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api_start_control",
            "title": "启动任务控制验证",
            "goal": "验证 core-api 启动任务动作入口。",
            "status": "draft",
        },
    )
    assert created_task.status_code == 201

    start_response = client.post(
        "/tasks/task_api_start_control/start",
        json={
            "currentFocus": "通过 core-api 启动正式执行",
            "currentObjective": "进入运行队列。",
        },
    )
    assert start_response.status_code == 202
    start_payload = start_response.json()
    assert start_payload["status"] == "queued"
    assert start_payload["workItem"]["command"] == "start"
    assert start_payload["task"]["status"] == "queued"

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_api_pause_control",
                "title": "暂停任务控制验证",
                "goal": "验证 core-api 暂停请求动作入口。",
                "status": "running",
                "resumeMessage": "等待 safe-stop 后恢复。",
            }
        )

    pause_response = client.post(
        "/tasks/task_api_pause_control/pause-request",
        json={
            "reason": "manual-safe-stop-request",
            "resumeMessage": "等待 safe-stop 后恢复。",
        },
    )
    assert pause_response.status_code == 202
    pause_payload = pause_response.json()
    assert pause_payload["status"] == "pause-requested"
    assert pause_payload["task"]["status"] == "pause-requested"

    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        paused_task = task_repository.create_task(
            {
                "id": "task_api_resume_control",
                "title": "恢复任务控制验证",
                "goal": "验证 core-api 恢复动作入口。",
                "status": "paused",
                "resumeMessage": "从 safe-stop 继续。",
            }
        )
        paused_run = task_repository.create_agent_run(
            paused_task.id,
            {
                "id": "run_api_resume_control",
                "status": "paused",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        paused_snapshot = task_repository.create_snapshot(
            TaskSnapshotSummary(
                id="snapshot_api_resume_control",
                appId=paused_task.app_id,
                taskId=paused_task.id,
                agentRunId=paused_run.id,
                projectId=paused_task.project_id,
                branchId=paused_task.branch_id,
                snapshotType="pause",
                status="restorable",
                resumeToken="resume_api_resume_control",
                contextRef={"type": "package-entry", "locator": f"runtime/tasks/{paused_task.id}/snapshots/context"},
                rootMountRef={"type": "package-entry", "locator": f"runtime/tasks/{paused_task.id}/snapshots/root-mount"},
                pendingWrites=[],
                pendingActions=[],
                resumeMessage="从 safe-stop 继续。",
                safeStopReason="manual-safe-stop",
                createdAt=utc_now(),
                safeToPause=True,
                blockers=[],
            )
        )
        task_repository.update_task(
            paused_task.id,
            {
                "status": "paused",
                "activeSnapshotId": paused_snapshot.id,
                "pauseRequested": False,
            },
        )

    resume_response = client.post(
        "/tasks/task_api_resume_control/resume",
        json={
            "resumeToken": "resume_api_resume_control",
            "resumeMessage": "从 safe-stop 继续。",
        },
    )
    assert resume_response.status_code == 202
    resume_payload = resume_response.json()
    assert resume_payload["status"] == "queued"
    assert resume_payload["workItem"]["command"] == "resume"
    assert resume_payload["task"]["status"] == "queued"

    overview_response = client.get("/workbench/overview")
    assert overview_response.status_code == 200
    overview_cards = overview_response.json()["cards"]
    assert overview_cards["pausedTasks"] >= 0
    assert overview_cards["restorableSnapshots"] >= 1


def test_core_api_exposes_m9_resource_and_prompt_control_planes() -> None:
    asset_response = client.post(
        "/assets/ingest",
        json={
            "mediaType": "document",
            "sourceText": "正式控制面测试需要暴露资产、训练实验和 Prompt 编译资源，并保留可审计的来源。",
            "spaceId": "space_default",
            "branchId": "branch_main",
        },
    )
    assert asset_response.status_code == 201
    asset_payload = asset_response.json()
    asset_id = asset_payload["asset"]["id"]
    assert asset_payload["segmentCount"] >= 1

    asset_list = client.get("/assets", params={"limit": 50})
    assert asset_list.status_code == 200
    assert any(asset["id"] == asset_id for asset in asset_list.json()["assets"])

    asset_detail = client.get(f"/assets/{asset_id}")
    assert asset_detail.status_code == 200
    assert len(asset_detail.json()["segments"]) >= 1
    assert asset_detail.json()["sourcePayload"]["assetId"] == asset_id

    dataset_response = client.post(
        "/training/dataset-versions/prepare",
        json={
            "datasetName": "api_control_plane_dataset",
            "maxRows": 8,
            "includeMemoryNodes": True,
        },
    )
    assert dataset_response.status_code == 201
    dataset_payload = dataset_response.json()
    dataset_id = dataset_payload["datasetVersion"]["id"]
    assert dataset_payload["datasetVersion"]["rowCount"] >= 1

    dataset_list = client.get("/training/dataset-versions", params={"limit": 50})
    assert dataset_list.status_code == 200
    assert any(version["id"] == dataset_id for version in dataset_list.json()["datasetVersions"])

    dataset_detail = client.get(f"/training/dataset-versions/{dataset_id}")
    assert dataset_detail.status_code == 200
    assert len(dataset_detail.json()["previewRows"]) >= 1

    model_artifact_response = client.post(
        "/training/model-artifacts/stage",
        json={
            "datasetVersionId": dataset_id,
            "baseModel": "gpt-5.4",
            "tuningMethod": "distillation",
            "minimumRows": 1,
        },
    )
    assert model_artifact_response.status_code == 201
    model_artifact_id = model_artifact_response.json()["modelArtifact"]["id"]

    model_artifacts = client.get("/training/model-artifacts", params={"limit": 50})
    assert model_artifacts.status_code == 200
    assert any(artifact["id"] == model_artifact_id for artifact in model_artifacts.json()["modelArtifacts"])

    model_artifact_detail = client.get(f"/training/model-artifacts/{model_artifact_id}")
    assert model_artifact_detail.status_code == 200
    assert model_artifact_detail.json()["metrics"]["artifactId"] == model_artifact_id

    workspace_root = resolve_workspace_root()
    prompt_dir = ensure_state_subdir("tests/prompt-control-plane", workspace_root)
    compiled_messages_path = prompt_dir / "compiled.json"
    request_path = prompt_dir / "request.json"
    response_path = prompt_dir / "response.json"
    write_json(compiled_messages_path, {"messages": [{"role": "user", "content": "列出 Prompt 控制面的关键能力。"}]})
    write_json(request_path, {"input": "prompt control plane"})
    write_json(response_path, {"rawResponse": {"text": "控制面需要显示 profile、seed template、tool 和 compiled prompt。"}})

    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        prompt_repository = PromptAssetRepository(session)
        runtime_repository = RuntimeRepository(session)
        _seed_prompt_profile_version(
            prompt_repository,
            version_id="prompt_profile_api_control_plane",
            prompt_profile_id="yggdrasil.prompt-control-plane.fixture",
        )
        _seed_seed_template_version(
            prompt_repository,
            version_id="seed_api_control_plane",
            seed_template_id="yggdrasil.seed.control-plane.fixture",
        )
        artifact = prompt_repository.create_prompt_compile_artifact(
            {
                "projectId": "project_default",
                "promptProfileVersionId": "prompt_profile_api_control_plane",
                "seedTemplateVersionId": "seed_api_control_plane",
                "runType": "main",
                "taskType": "coding",
                "registeredTools": [{"name": "training_lab.prepare_dataset"}],
                "compiledMessagesRef": {
                    "type": "file",
                    "locator": relative_workspace_path(compiled_messages_path, workspace_root),
                },
                "contentHash": "api-control-plane",
            }
        )
        runtime_repository.create_model_invocation(
            {
                "projectId": "project_default",
                "requestedModel": "gpt-5.4",
                "requestedProvider": "copilot",
                "resolvedModel": "gpt-5.4",
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
                "inputTokensUsed": 64,
                "outputTokensUsed": 96,
                "costUsed": 0.01,
            }
        )

    prompt_profiles = client.get("/prompting/prompt-profiles", params={"appId": "yggdrasil.app.software-factory"})
    assert prompt_profiles.status_code == 200
    assert any(profile["id"] == "yggdrasil.software-factory.main-agent" for profile in prompt_profiles.json()["promptProfiles"])

    seed_templates = client.get("/prompting/seed-templates", params={"appId": "yggdrasil.app.software-factory"})
    assert seed_templates.status_code == 200
    assert any(template["id"] == "yggdrasil.seed.coding.inherit-project" for template in seed_templates.json()["seedTemplates"])

    applications = client.get("/applications")
    assert applications.status_code == 200
    app_ids = {item["application"]["appId"] for item in applications.json()["applications"]}
    assert {
        "yggdrasil.app.base",
        "yggdrasil.app.software-factory",
        "yggdrasil.app.knowledge-studio",
        "yggdrasil.app.coding-greenfield",
        "yggdrasil.app.coding-inherit",
        "yggdrasil.app.deep-research",
        "yggdrasil.app.epic-writing",
        "yggdrasil.app.maintenance-ops",
        "yggdrasil.app.learning-coach",
        "yggdrasil.app.scenic-guide",
    } <= app_ids

    application_detail = client.get("/applications/yggdrasil.app.software-factory")
    assert application_detail.status_code == 200
    assert application_detail.json()["application"]["appId"] == "yggdrasil.app.software-factory"
    assert application_detail.json()["effectiveConfig"]["defaultTaskType"] == "coding"

    registered_tools = client.get(
        "/prompting/registered-tools",
        params={"appId": "yggdrasil.app.software-factory"},
    )
    assert registered_tools.status_code == 200
    assert "mcp-bridge" in registered_tools.json()["activeCapabilities"]
    assert any(tool["name"] == "mcp.read.read_file" for tool in registered_tools.json()["registeredTools"])

    mcp_state = client.get("/mcp")
    assert mcp_state.status_code == 200
    assert {"workspace-read", "workspace-edit", "workspace-search", "workspace-execute", "workspace-python"} <= {
        server["id"] for server in mcp_state.json()["servers"]
    }
    assert any(tool["exposedName"] == "mcp.read.read_file" for tool in mcp_state.json()["tools"])

    mcp_workspace = client.post("/mcp/workspace", json={"projectWorkspace": workspace_root.as_posix()})
    assert mcp_workspace.status_code == 200
    assert Path(mcp_workspace.json()["projectWorkspace"]).resolve() == workspace_root.resolve()

    compile_artifacts = client.get("/prompting/compile-artifacts", params={"limit": 50})
    assert compile_artifacts.status_code == 200
    assert any(item["id"] == artifact.id for item in compile_artifacts.json()["promptCompileArtifacts"])

    compile_artifact_detail = client.get(f"/prompting/compile-artifacts/{artifact.id}")
    assert compile_artifact_detail.status_code == 200
    assert compile_artifact_detail.json()["compiledMessages"]["messages"][0]["role"] == "user"
    assert compile_artifact_detail.json()["requestPayload"]["input"] == "prompt control plane"

    preview = client.post(
        "/prompting/compile-preview",
        json={
            "appId": "yggdrasil.app.software-factory",
            "runType": "main",
            "taskType": "coding",
            "activeCapabilities": ["text-memory", "shared-memory", "training-lab"],
            "task": {
                "title": "Prompt Preview",
                "goal": "验证 Prompt 编译控制面。",
                "currentFocus": "prompt-ops",
                "currentObjective": "显示 profile、seed 和工具清单。",
                "resumeMessage": "继续查看 Prompt 控制面。",
            },
            "request": {
                "currentFocus": "prompt-ops",
                "currentObjective": "显示 profile、seed 和工具清单。",
                "responseRequirements": "需要先给结论，再给下一步。",
            },
        },
    )
    assert preview.status_code == 201
    preview_payload = preview.json()["compiledPrompt"]
    assert preview_payload["appId"] == "yggdrasil.app.software-factory"
    assert preview_payload["promptProfileId"] == "yggdrasil.software-factory.main-agent"
    assert preview_payload["seedTemplateId"] == "yggdrasil.seed.coding.inherit-project"
    assert len(preview_payload["registeredTools"]) >= 1
    assert len(preview_payload["messages"]) == 2

    learning_preview = client.post(
        "/prompting/compile-preview",
        json={
            "appId": "yggdrasil.app.learning-coach",
            "task": {
                "title": "学习辅导预览",
                "goal": "验证学习辅导应用默认 prompt 装配。",
            },
            "request": {
                "currentFocus": "learning-state",
                "currentObjective": "建立用户学习画像并规划下一步。",
            },
        },
    )
    assert learning_preview.status_code == 201
    learning_payload = learning_preview.json()["compiledPrompt"]
    assert learning_payload["appId"] == "yggdrasil.app.learning-coach"
    assert learning_payload["taskType"] == "learning"
    assert learning_payload["promptProfileId"] == "yggdrasil.learning-coach.main-agent"
    assert learning_payload["seedTemplateId"] == "yggdrasil.seed.learning.coach"

    scenic_preview = client.post(
        "/prompting/compile-preview",
        json={
            "appId": "yggdrasil.app.scenic-guide",
            "task": {
                "title": "景区导览预览",
                "goal": "验证景区导览应用默认 prompt 装配。",
            },
            "request": {
                "currentFocus": "visitor-service",
                "currentObjective": "根据游客约束生成导览建议。",
            },
        },
    )
    assert scenic_preview.status_code == 201
    scenic_payload = scenic_preview.json()["compiledPrompt"]
    assert scenic_payload["appId"] == "yggdrasil.app.scenic-guide"
    assert scenic_payload["taskType"] == "service"
    assert scenic_payload["promptProfileId"] == "yggdrasil.scenic-guide.main-agent"
    assert scenic_payload["seedTemplateId"] == "yggdrasil.seed.scenic.guide"

    activate = client.post("/applications/yggdrasil.app.software-factory/activate")
    assert activate.status_code == 200
    assert activate.json()["configBinding"]["active"] is True

    config_update = client.post(
        "/applications/yggdrasil.app.software-factory/config",
        json={"importantConfig": {"codeReview": {"requireTests": False}}},
    )
    assert config_update.status_code == 200
    assert config_update.json()["configBinding"]["importantConfig"]["codeReview"]["requireTests"] is False


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