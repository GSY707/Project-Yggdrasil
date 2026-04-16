from __future__ import annotations

from fastapi.testclient import TestClient

from yggdrasil_core_api.app import app
from yggdrasil_sdk import TaskRepository, get_persistence_runtime
from yggdrasil_sdk.persistence.repositories import RuntimeRepository, WorkspaceBootstrapRepository


client = TestClient(app)


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