from __future__ import annotations

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
    utc_now,
)
from yggdrasil_sdk.persistence.constants import DEFAULT_APP_ID
from yggdrasil_sdk.persistence.repositories import RuntimeRepository, WorkspaceBootstrapRepository
from yggdrasil_sdk.support import ensure_state_subdir, write_json


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


def test_repository_persists_fork_agent_run_fields_and_active_count() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_fork_run_fields",
                "title": "Fork run 字段持久化测试",
                "goal": "验证 fork run 可以审计和恢复。",
                "status": "queued",
            }
        )
        parent = task_repository.create_agent_run(
            "task_fork_run_fields",
            {
                "id": "run_fork_parent",
                "runType": "main",
                "status": "running",
            },
        )
        fork = task_repository.create_agent_run(
            "task_fork_run_fields",
            {
                "id": "run_fork_child_a",
                "parentRunId": parent.id,
                "runType": "fork",
                "status": "running",
                "forkRootRunId": parent.id,
                "forkDepth": 1,
                "assignedWorkTreeNodeId": "wt-child-a",
                "parentContextAnchor": "ctx-anchor-parent-1",
                "forkGroupId": "fork-group-1",
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
            },
        )

        assert fork.run_type == "fork"
        assert fork.parent_run_id == parent.id
        assert fork.fork_root_run_id == parent.id
        assert fork.fork_depth == 1
        assert fork.assigned_work_tree_node_id == "wt-child-a"
        assert fork.parent_context_anchor == "ctx-anchor-parent-1"
        assert fork.fork_group_id == "fork-group-1"
        assert task_repository.count_active_fork_runs("task_fork_run_fields", fork_root_run_id=parent.id) == 1

        completed = task_repository.update_agent_run(fork.id, {"status": "completed"})
        assert completed.status == "completed"
        assert task_repository.count_active_fork_runs("task_fork_run_fields", fork_root_run_id=parent.id) == 0

        listed = {run.id: run for run in task_repository.list_agent_runs("task_fork_run_fields")}
        assert listed[fork.id].assigned_work_tree_node_id == "wt-child-a"
        assert listed[fork.id].parent_context_anchor == "ctx-anchor-parent-1"


def test_repository_rejects_incomplete_fork_agent_run_fields() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_fork_required_fields",
                "title": "Fork run 必填字段测试",
                "goal": "验证 fork run 不允许缺少恢复所需字段。",
                "status": "queued",
            }
        )
        parent = task_repository.create_agent_run(
            "task_fork_required_fields",
            {
                "id": "run_fork_required_parent",
                "runType": "main",
                "status": "running",
            },
        )

        with pytest.raises(ValueError, match="runType=fork requires assignedWorkTreeNodeId"):
            task_repository.create_agent_run(
                "task_fork_required_fields",
                {
                    "id": "run_fork_missing_node",
                    "parentRunId": parent.id,
                    "runType": "fork",
                    "status": "running",
                    "forkRootRunId": parent.id,
                    "forkDepth": 1,
                    "parentContextAnchor": "ctx-required",
                    "forkGroupId": "fork-required",
                },
            )

        with pytest.raises(ValueError, match="runType=fork requires forkDepth >= 1"):
            task_repository.create_agent_run(
                "task_fork_required_fields",
                {
                    "id": "run_fork_depth_zero",
                    "parentRunId": parent.id,
                    "runType": "fork",
                    "status": "running",
                    "forkRootRunId": parent.id,
                    "forkDepth": 0,
                    "assignedWorkTreeNodeId": "wt-required-child",
                    "parentContextAnchor": "ctx-required",
                    "forkGroupId": "fork-required",
                },
            )


def test_repository_rejects_clearing_required_fork_agent_run_fields() -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        task_repository.create_task(
            {
                "id": "task_fork_required_update",
                "title": "Fork run 必填字段更新测试",
                "goal": "验证 fork run 不允许在更新时清空恢复字段。",
                "status": "queued",
            }
        )
        parent = task_repository.create_agent_run(
            "task_fork_required_update",
            {
                "id": "run_fork_required_update_parent",
                "runType": "main",
                "status": "running",
            },
        )
        fork = task_repository.create_agent_run(
            "task_fork_required_update",
            {
                "id": "run_fork_required_update_child",
                "parentRunId": parent.id,
                "runType": "fork",
                "status": "running",
                "forkRootRunId": parent.id,
                "forkDepth": 1,
                "assignedWorkTreeNodeId": "wt-required-update-child",
                "parentContextAnchor": "ctx-required-update",
                "forkGroupId": "fork-required-update",
            },
        )

        with pytest.raises(ValueError, match="runType=fork requires parentContextAnchor"):
            task_repository.update_agent_run(fork.id, {"parentContextAnchor": None})
        with pytest.raises(ValueError, match="runType=fork requires forkDepth >= 1"):
            task_repository.update_agent_run(fork.id, {"forkDepth": 0})


def test_core_api_returns_fork_agent_run_fields() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api_fork_run_fields",
            "title": "Fork run API 字段测试",
            "goal": "验证 fork run 字段会从 API 返回。",
            "status": "queued",
        },
    )
    assert created_task.status_code == 201

    parent_response = client.post(
        "/tasks/task_api_fork_run_fields/runs",
        json={
            "id": "run_api_fork_parent",
            "runType": "main",
            "status": "running",
        },
    )
    assert parent_response.status_code == 201

    fork_response = client.post(
        "/tasks/task_api_fork_run_fields/runs",
        json={
            "id": "run_api_fork_child",
            "parentRunId": "run_api_fork_parent",
            "runType": "fork",
            "status": "waiting-tool",
            "forkRootRunId": "run_api_fork_parent",
            "forkDepth": 2,
            "assignedWorkTreeNodeId": "wt-api-child",
            "parentContextAnchor": "ctx-api-anchor",
            "forkGroupId": "fork-api-group",
        },
    )
    assert fork_response.status_code == 201
    fork_payload = fork_response.json()["run"]
    assert fork_payload["runType"] == "fork"
    assert fork_payload["forkRootRunId"] == "run_api_fork_parent"
    assert fork_payload["forkDepth"] == 2
    assert fork_payload["assignedWorkTreeNodeId"] == "wt-api-child"
    assert fork_payload["parentContextAnchor"] == "ctx-api-anchor"
    assert fork_payload["forkGroupId"] == "fork-api-group"

    task_response = client.get("/tasks/task_api_fork_run_fields")
    assert task_response.status_code == 200
    runs = {run["id"]: run for run in task_response.json()["agentRuns"]}
    assert runs["run_api_fork_child"]["runType"] == "fork"
    assert runs["run_api_fork_child"]["assignedWorkTreeNodeId"] == "wt-api-child"


def test_core_api_rejects_incomplete_fork_agent_run_fields() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api_fork_required_fields",
            "title": "Fork run API 必填字段测试",
            "goal": "验证 API 不允许创建缺字段 fork run。",
            "status": "queued",
        },
    )
    assert created_task.status_code == 201

    parent_response = client.post(
        "/tasks/task_api_fork_required_fields/runs",
        json={
            "id": "run_api_fork_required_parent",
            "runType": "main",
            "status": "running",
        },
    )
    assert parent_response.status_code == 201

    fork_response = client.post(
        "/tasks/task_api_fork_required_fields/runs",
        json={
            "id": "run_api_fork_required_missing_group",
            "parentRunId": "run_api_fork_required_parent",
            "runType": "fork",
            "status": "running",
            "forkRootRunId": "run_api_fork_required_parent",
            "forkDepth": 1,
            "assignedWorkTreeNodeId": "wt-api-required-child",
            "parentContextAnchor": "ctx-api-required",
        },
    )
    assert fork_response.status_code == 409
    assert "runType=fork requires forkGroupId" in fork_response.json()["detail"]


def _seed_llm_work_runtime_case(*, task_id: str, run_id: str, invocation_id: str) -> None:
    runtime = get_persistence_runtime()
    with runtime.session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        task_repository.create_task(
            {
                "id": task_id,
                "title": "LLM 工作分析 API 测试任务",
                "goal": "验证 runtime analysis API 可以生成与查询分析工件。",
                "status": "running",
            }
        )
        run = task_repository.create_agent_run(
            task_id,
            {
                "id": run_id,
                "status": "completed",
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
                "windowIndex": 1,
                "restartCount": 0,
            },
        )
        runtime_repository.create_model_invocation(
            {
                "id": invocation_id,
                "projectId": "project_default",
                "taskId": task_id,
                "agentRunId": run.id,
                "requestedModel": "LongCat-2.0",
                "requestedProvider": "longcat",
                "resolvedModel": "LongCat-2.0",
                "resolvedProvider": "longcat",
                "status": "completed",
                "assistantTextSummary": "API 路由测试用调用。",
                "inputTokensUsed": 96,
                "outputTokensUsed": 48,
                "costUsed": 0.05,
                "latencyMs": 120.0,
                "startedAt": utc_now(),
                "endedAt": utc_now(),
                "createdAt": utc_now(),
            }
        )

    request_path = ensure_state_subdir("llm/requests") / f"{invocation_id}.json"
    response_path = ensure_state_subdir("llm/responses") / f"{invocation_id}.json"
    metrics_path = ensure_state_subdir("runtime/metrics") / f"{invocation_id}.json"
    takeover_path = ensure_state_subdir("runtime/takeover") / f"{task_id}-{run_id}.json"
    work_context_path = ensure_state_subdir("runtime/work-context-stack") / f"{task_id}-{run_id}.json"
    window_path = ensure_state_subdir("runtime/window-executions") / f"{task_id}-{run_id}.json"
    window_history_path = ensure_state_subdir("runtime/window-executions/by-invocation") / f"{invocation_id}.json"

    write_json(
        request_path,
        {
            "invocationId": invocation_id,
            "taskId": task_id,
            "agentRunId": run_id,
            "auditLevel": "default",
            "toolSpecs": [{"name": "read_file", "description": "Read a file", "parameterCount": 1}],
        },
    )
    write_json(
        response_path,
        {
            "invocationId": invocation_id,
            "taskId": task_id,
            "agentRunId": run_id,
            "auditLevel": "default",
            "mode": "live",
            "provider": "longcat",
            "model": "LongCat-2.0",
            "finishReason": "stop",
            "assistantText": "API 分析已完成。",
            "usage": {
                "inputTokens": 96,
                "outputTokens": 48,
                "totalTokens": 144,
                "cacheHitInputTokens": 72,
                "cacheWriteInputTokens": 6,
                "nonCacheInputTokens": 18,
            },
            "costUsed": 0.05,
            "toolExecutionSummaries": [
                {"tool": "read_file", "success": True, "status": "ok", "resultPreview": "README.md"}
            ],
            "rounds": [
                {
                    "index": 0,
                    "mode": "live",
                    "finishReason": "stop",
                    "latencyMs": 120.0,
                    "reasoningContentPresent": False,
                    "toolCalls": [],
                    "toolFailures": [],
                }
            ],
            "runtimeMetrics": {
                "windowIndex": 1,
                "restartCount": 0,
                "cumulativeWindowSpanTokens": 900,
            },
        },
    )
    write_json(
        metrics_path,
        {
            "taskId": task_id,
            "invocationId": invocation_id,
            "snapshot": {
                "windowIndex": 1,
                "restartCount": 0,
                "cacheHitInputTokens": 72,
                "cacheWriteInputTokens": 6,
                "nonCacheInputTokens": 18,
                "cumulativeWindowSpanTokens": 900,
            },
        },
    )
    write_json(
        takeover_path,
        {"workTree": {"currentNodeId": "wt-api-node", "status": "active", "recoveryAnchor": "resume:wt-api-node"}},
    )
    write_json(
        work_context_path,
        {
            "frames": [
                {
                    "id": "frame-api",
                    "nodeId": "wt-api-node",
                    "frameHeader": "API 调试节点",
                    "cursorState": "resume:api",
                }
            ]
        },
    )
    window_record = {
        "taskId": task_id,
        "runId": run_id,
        "agentRunId": run_id,
        "invocationId": invocation_id,
        "windowIndex": 1,
        "transitionStage": "task-complete",
        "transitionOutcome": "awaiting-approval",
        "currentObjective": "验证 API 分析入口",
        "currentFocus": "生成 latest analysis",
        "workTreeCurrentNodeId": "wt-api-node",
        "workTreeStatus": "awaiting-approval",
        "workTreeRecoveryAnchor": "resume:wt-api-node",
        "topFrameId": "frame-api",
        "topFramePrefixCacheKey": "api-prefix-1",
        "memoryRetrievalState": {"matchedNodeCount": 2, "materializedNodeCount": 0, "retrievalFingerprint": "api-fp"},
        "cacheSummary": {
            "inputTokens": 96,
            "cacheHitInputTokens": 72,
            "cacheWriteInputTokens": 6,
            "nonCacheInputTokens": 18,
            "trackedInputTokens": 96,
            "cacheHitRatio0_1": 0.75,
            "cacheWriteRatio0_1": 0.0625,
        },
        "workTreeDebug": {
            "topFrameId": "frame-api",
            "topFrameNodeId": "wt-api-node",
            "topFramePrefixCacheKey": "api-prefix-1",
            "continuationReason": "resume:api",
            "approvalStop0_1": 1,
            "childBubble0_1": 0,
            "mixedOutcome0_1": 0,
        },
        "llm": {"planningStub0_1": 0},
    }
    write_json(window_path, window_record)
    write_json(window_history_path, window_record)

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
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
            },
        )
        decision = runtime_repository.create_model_route_decision(
            {
                "taskId": "task_api_llm",
                "agentRunId": run.id,
                "selectedModel": "LongCat-2.0",
                "selectedProvider": "longcat",
                "candidateModels": [{"model": "LongCat-2.0", "provider": "longcat"}],
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
                "requestedModel": "LongCat-2.0",
                "requestedProvider": "longcat",
                "resolvedModel": "LongCat-2.0",
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


def test_core_api_exposes_task_mailbox_and_side_channel() -> None:
    created_task = client.post(
        "/tasks",
        json={
            "id": "task_api_mailbox",
            "title": "邮箱与侧信道 API 测试",
            "goal": "验证 runtime mailbox 与 side-channel 已走正式持久化链路。",
            "status": "queued",
        },
    )
    assert created_task.status_code == 201

    mailbox_response = client.post(
        "/runtime/tasks/task_api_mailbox/mailbox",
        json={
            "sender": {"type": "agent", "id": "subagent"},
            "messageKind": "subagent-completion",
            "subject": "Child finished integration slice",
            "body": "Child completed implementation and is waiting for parent summarization.",
            "workTreeNodeId": "wt-node-mailbox",
            "wakeOnMessage": True,
        },
    )
    assert mailbox_response.status_code == 201
    mailbox_payload = mailbox_response.json()
    assert mailbox_payload["mailboxMessage"]["messageKind"] == "subagent-completion"
    assert mailbox_payload["mailboxState"]["pendingCount"] == 1
    assert mailbox_payload["sideChannelEvent"]["eventKind"] == "mailbox.subagent-completion"

    list_mailbox = client.get("/runtime/tasks/task_api_mailbox/mailbox")
    assert list_mailbox.status_code == 200
    assert list_mailbox.json()["mailboxState"]["pendingCount"] == 1
    assert len(list_mailbox.json()["mailboxMessages"]) == 1

    side_channel_response = client.post(
        "/runtime/tasks/task_api_mailbox/side-channel",
        json={
            "source": {"type": "module", "id": "runtime-kernel"},
            "eventKind": "context-warning",
            "level": "warning",
            "summary": "Context window is nearing the restart threshold.",
            "workTreeNodeId": "wt-node-mailbox",
        },
    )
    assert side_channel_response.status_code == 201
    assert side_channel_response.json()["sideChannelEvent"]["eventKind"] == "context-warning"

    list_side_channel = client.get("/runtime/tasks/task_api_mailbox/side-channel")
    assert list_side_channel.status_code == 200
    event_kinds = {item["eventKind"] for item in list_side_channel.json()["sideChannelEvents"]}
    assert "mailbox.subagent-completion" in event_kinds
    assert "context-warning" in event_kinds

    task_detail = client.get("/tasks/task_api_mailbox")
    assert task_detail.status_code == 200
    detail_payload = task_detail.json()
    assert detail_payload["mailboxState"]["pendingCount"] == 1
    assert len(detail_payload["mailboxMessages"]) == 1
    assert len(detail_payload["sideChannelEvents"]) >= 2


def test_core_api_generates_and_reads_llm_work_analysis() -> None:
    task_id = "task_api_llm_work"
    run_id = "run_api_llm_work"
    invocation_id = "llm_api_llm_work"
    _seed_llm_work_runtime_case(task_id=task_id, run_id=run_id, invocation_id=invocation_id)

    create_response = client.post(
        "/runtime/analysis/runs",
        json={
            "taskId": task_id,
            "granularity": "run,window,tool",
            "persist": True,
        },
    )
    assert create_response.status_code == 200
    created_payload = create_response.json()
    assert created_payload["summary"]["windowCount"] == 1
    assert created_payload["summary"]["cacheSummary"]["cacheHitInputTokens"] == 72
    assert len(created_payload["windows"]) == 1
    assert len(created_payload["tools"]) == 1

    analysis_id = created_payload["analysis"]["analysisId"]
    read_response = client.get(f"/runtime/analysis/runs/{analysis_id}", params={"granularity": "artifact"})
    assert read_response.status_code == 200
    read_payload = read_response.json()
    assert "artifacts" in read_payload
    assert "windows" not in read_payload

    latest_response = client.get(f"/tasks/{task_id}/analysis/latest", params={"granularity": "window"})
    assert latest_response.status_code == 200
    latest_payload = latest_response.json()
    assert len(latest_payload["windows"]) == 1
    assert latest_payload["windows"][0]["invocationId"] == invocation_id
    assert latest_payload["windows"][0]["topFramePrefixCacheKey"] == "api-prefix-1"


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
    assert runtime_control["canSaveSnapshot"] is True
    assert runtime_control["canCancel"] is True
    assert runtime_control["activeSnapshotId"] == "snapshot_api_resume"
    assert "recommendedResumeToken" not in runtime_control
    assert runtime_control["latestRestorableSnapshot"]["safeStopReason"] == "manual-safe-stop"
    assert runtime_control["activeSnapshot"]["retentionClass"] == "active-paused"
    assert runtime_control["latestRestorableSnapshot"]["appId"] == DEFAULT_APP_ID


