from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
import pytest
import yggdrasil_sdk.runtime_kernel.takeover as runtime_takeover

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
from yggdrasil_sdk.contracts import TaskTakeoverProtocol
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


def _awaiting_approval_takeover_protocol(task_id: str) -> dict[str, object]:
    return {
        "id": f"takeover_{task_id}",
        "version": "0.1.0",
        "taskId": task_id,
        "taskType": "coding",
        "runType": "main",
        "currentPhase": "deliver",
        "status": "verified",
        "objective": "完成最终交付并等待人工批准。",
        "objectiveSummary": "两个子节点已经完成，当前停在根节点等待批准。",
        "ambiguities": [],
        "constraints": [],
        "plan": [],
        "workTree": {
            "version": "0.2.0",
            "id": f"work_tree_{task_id}",
            "taskId": task_id,
            "rootNodeId": "root",
            "rootObjective": "完成最终交付并等待人工批准。",
            "status": "awaiting-approval",
            "currentNodeId": "root",
            "loadedNodeIds": ["root", "child-1", "child-2"],
            "activePathNodeIds": ["root"],
            "pcMemo": "等待批准",
            "entropyBudgetRemaining": 6,
            "versionCounter": 3,
            "nodes": [
                {
                    "id": "root",
                    "title": "最终交付",
                    "parentNodeId": None,
                    "questionsItAnswers": ["最终结果是什么"],
                    "nodeText": "整合两个子节点输出为最终答案。",
                    "localGoal": "整合两个子节点输出为最终答案。",
                    "workingNodeAnnotation": "<Working_Node: root>",
                    "executionSummary": "根节点已经整合两个子节点并形成最终答案。",
                    "phase": "delivery",
                    "status": "completed",
                    "childNodeIds": ["child-1", "child-2"],
                    "recoveryAnchor": "resume:root",
                },
                {
                    "id": "child-1",
                    "title": "第一段证据",
                    "parentNodeId": "root",
                    "questionsItAnswers": ["第一段证据是否齐全"],
                    "nodeText": "整理第一段证据。",
                    "localGoal": "整理第一段证据。",
                    "workingNodeAnnotation": "<Working_Node: child-1>",
                    "executionSummary": "第一段证据已齐全。",
                    "phase": "executing",
                    "status": "completed",
                    "childNodeIds": [],
                    "recoveryAnchor": "resume:child-1",
                },
                {
                    "id": "child-2",
                    "title": "第二段证据",
                    "parentNodeId": "root",
                    "questionsItAnswers": ["第二段证据是否齐全"],
                    "nodeText": "整理第二段证据。",
                    "localGoal": "整理第二段证据。",
                    "workingNodeAnnotation": "<Working_Node: child-2>",
                    "executionSummary": "第二段证据已齐全。",
                    "phase": "executing",
                    "status": "completed",
                    "childNodeIds": [],
                    "recoveryAnchor": "resume:child-2",
                },
            ],
        },
        "deliverySections": [],
        "verificationItems": [],
        "metrics": {
            "planQualityScore0_100": 95.0,
            "reworkCount": 0,
            "reworkRate": 0.0,
            "clarificationNeeded": False,
            "deliveryCompletenessScore0_100": 100.0,
            "verificationPassRate": 1.0,
        },
        "appliedModules": ["task-takeover"],
        "hookTrace": [],
    }


def _seed_awaiting_approval_task(task_id: str, run_id: str) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task = task_repository.create_task(
            {
                "id": task_id,
                "title": f"{task_id} awaiting approval",
                "goal": "验证 awaiting-approval 控制面。",
                "status": "awaiting-approval",
                "currentObjective": "等待批准或重新打开修订。",
                "currentFocus": "awaiting-approval",
            }
        )
        task_repository.create_agent_run(
            task.id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": "gpt-5.4",
                "selectedProvider": "copilot",
            },
        )
        runtime_takeover.persist_task_takeover_protocol(
            TaskTakeoverProtocol.model_validate(_awaiting_approval_takeover_protocol(task_id)),
            task_id=task.id,
            run_id=run_id,
        )


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


def test_core_api_exposes_awaiting_approval_controls() -> None:
    _seed_awaiting_approval_task("task_api_approve_completion", "run_api_approve_completion")
    detail_response = client.get("/tasks/task_api_approve_completion")
    assert detail_response.status_code == 200
    runtime_control = detail_response.json()["runtimeControl"]
    assert runtime_control["canApprove"] is True
    assert runtime_control["canRequestRevision"] is True
    assert runtime_control["recommendedRevisionNodeId"] == "root"

    approve_response = client.post("/tasks/task_api_approve_completion/approve-completion")
    assert approve_response.status_code == 200
    approve_payload = approve_response.json()
    assert approve_payload["status"] == "completed"
    assert approve_payload["task"]["status"] == "completed"
    assert approve_payload["takeoverProtocol"]["workTree"]["status"] == "completed"

    _seed_awaiting_approval_task("task_api_request_revision", "run_api_request_revision")
    revision_response = client.post(
        "/tasks/task_api_request_revision/request-revision",
        json={
            "nodeId": "child-2",
            "reason": "补充第二段证据。",
        },
    )
    assert revision_response.status_code == 202
    revision_payload = revision_response.json()
    assert revision_payload["status"] == "queued"
    assert revision_payload["task"]["status"] == "queued"
    assert revision_payload["workItem"]["command"] == "start"
    assert revision_payload["workItem"]["payload"]["currentNodeId"] == "child-2"
    assert revision_payload["workItem"]["payload"]["topFrameId"] == "frame-child-2"
    assert revision_payload["takeoverProtocol"]["workTree"]["currentNodeId"] == "child-2"
    assert revision_payload["takeoverProtocol"]["workTree"]["status"] == "active"


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


