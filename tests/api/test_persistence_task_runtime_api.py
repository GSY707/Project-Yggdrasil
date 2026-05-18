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


