from __future__ import annotations

from fastapi.testclient import TestClient

from yggdrasil_core_api.app import app


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