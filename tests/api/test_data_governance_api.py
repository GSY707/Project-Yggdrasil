from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa
from fastapi.testclient import TestClient
import pytest

from yggdrasil_core_api.app import app
from yggdrasil_core_api.services import get_workspace_service
from yggdrasil_sdk import (
    OutboxRepository,
    RuntimeRepository,
    TaskRepository,
    get_persistence_runtime,
    utc_now,
)
from yggdrasil_sdk.persistence.orm import (
    AgentRunORM,
    MailboxMessageORM,
    ModelInvocationORM,
    ModelRouteDecisionORM,
    OutboxRecordORM,
    SideChannelEventORM,
    TaskORM,
)
from yggdrasil_sdk.persistence.repositories import WorkspaceBootstrapRepository
from yggdrasil_sdk.support import resolve_state_root, write_json


client = TestClient(app)
pytestmark = pytest.mark.slow


def _seed_task_runtime_case(*, task_id: str, status: str = "completed") -> tuple[str, str]:
    request_path = resolve_state_root() / "state" / "llm" / "requests" / f"{task_id}-request.json"
    response_path = resolve_state_root() / "state" / "llm" / "responses" / f"{task_id}-response.json"
    write_json(request_path, {"taskId": task_id, "kind": "request"})
    write_json(response_path, {"taskId": task_id, "kind": "response"})

    with get_persistence_runtime().session_scope() as session:
        WorkspaceBootstrapRepository(session).ensure_default_workspace()
        task_repository = TaskRepository(session)
        runtime_repository = RuntimeRepository(session)
        outbox_repository = OutboxRepository(session)

        task_repository.create_task(
            {
                "id": task_id,
                "title": "数据治理删除测试任务",
                "goal": "验证 task 级删除预览、审计和硬删除。",
                "status": status,
            }
        )
        run = task_repository.create_agent_run(
            task_id,
            {
                "id": f"run_{task_id}",
                "status": "completed",
                "selectedModel": "test-model",
                "selectedProvider": "test-provider",
            },
        )
        route = runtime_repository.create_model_route_decision(
            {
                "id": f"route_{task_id}",
                "taskId": task_id,
                "agentRunId": run.id,
                "selectedModel": "test-model",
                "selectedProvider": "test-provider",
                "candidateModels": ["test-model"],
            }
        )
        runtime_repository.create_model_invocation(
            {
                "id": f"invocation_{task_id}",
                "projectId": "project_default",
                "taskId": task_id,
                "agentRunId": run.id,
                "routeDecisionId": route.id,
                "requestedModel": "test-model",
                "requestedProvider": "test-provider",
                "resolvedModel": "test-model",
                "resolvedProvider": "test-provider",
                "status": "completed",
                "requestRef": {"type": "file", "locator": str(request_path)},
                "responseRef": {"type": "file", "locator": str(response_path)},
                "startedAt": utc_now(),
                "endedAt": utc_now(),
                "createdAt": utc_now(),
            }
        )
        runtime_repository.create_mailbox_message(
            {
                "id": f"mailbox_{task_id}",
                "taskId": task_id,
                "agentRunId": run.id,
                "messageKind": "test",
                "subject": "delete test",
                "body": "delete test",
            }
        )
        runtime_repository.create_side_channel_event(
            {
                "id": f"side_{task_id}",
                "taskId": task_id,
                "agentRunId": run.id,
                "eventKind": "test",
                "summary": "delete test",
            }
        )
        outbox_repository.record_event(
            {
                "id": f"outbox_{task_id}",
                "projectId": "project_default",
                "aggregateType": "task",
                "aggregateId": task_id,
                "eventType": "task.seeded",
                "payloadRef": {"type": "package-entry", "locator": f"tests/{task_id}"},
            }
        )
    return str(request_path), str(response_path)


def _row_count(model: object, where_clause: object | None = None) -> int:
    with get_persistence_runtime().session_scope() as session:
        statement = sa.select(sa.func.count()).select_from(model)
        if where_clause is not None:
            statement = statement.where(where_clause)
        return int(session.execute(statement).scalar_one() or 0)


def test_data_governance_manifest_exposes_local_and_remote_boundaries() -> None:
    response = client.get("/data-governance/manifest")

    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "data-governance-manifest-v0.1"
    assert payload["remoteBoundary"]["localModeUploadsToOfficialService"] is False
    assert {item["id"] for item in payload["assets"]} >= {"tasks", "runtime", "assets", "product-logs-backups"}


def test_data_governance_backup_routes_expose_snapshots_and_audit() -> None:
    class FakeBackupService:
        def list_data_governance_backups(self, *, limit: int = 20) -> dict[str, object]:
            assert limit == 2
            return {
                "backupRoot": "C:/tmp/yggdrasil-backups",
                "snapshots": [
                    {
                        "name": "20260606T010203Z",
                        "snapshotDir": "C:/tmp/yggdrasil-backups/20260606T010203Z",
                        "createdAt": "2026-06-06T01:02:03Z",
                        "databaseKind": "sqlite",
                    }
                ],
            }

        def create_data_governance_backup(self, payload: dict[str, object]) -> dict[str, object]:
            assert payload["reason"] == "web backup test"
            return {
                "backup": {
                    "name": "20260606T010203Z",
                    "snapshotDir": "C:/tmp/yggdrasil-backups/20260606T010203Z",
                    "createdAt": "2026-06-06T01:02:03Z",
                    "databaseKind": "sqlite",
                },
                "operation": {
                    "id": "operation_backup",
                    "operationType": "backup",
                    "scopeKind": "workspace",
                    "scopeId": None,
                    "dryRun": False,
                    "status": "completed",
                    "createdAt": "2026-06-06T01:02:03Z",
                    "executedAt": "2026-06-06T01:02:03Z",
                },
            }

    app.dependency_overrides[get_workspace_service] = lambda: FakeBackupService()
    try:
        list_response = client.get("/data-governance/backups?limit=2")
        create_response = client.post("/data-governance/backup", json={"reason": "web backup test"})
    finally:
        app.dependency_overrides.pop(get_workspace_service, None)

    assert list_response.status_code == 200
    assert list_response.json()["snapshots"][0]["databaseKind"] == "sqlite"
    assert create_response.status_code == 200
    assert create_response.json()["operation"]["operationType"] == "backup"


def test_task_deletion_plan_records_dry_run_operation() -> None:
    _seed_task_runtime_case(task_id="task_data_governance_plan")

    response = client.post(
        "/data-governance/deletion-plan",
        json={
            "scopeKind": "task",
            "scopeId": "task_data_governance_plan",
            "includeStateFiles": True,
            "reason": "test dry-run",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    plan = payload["plan"]
    table_counts = {item["table"]: item["count"] for item in plan["database"]["tables"]}
    assert table_counts["tasks"] == 1
    assert table_counts["agent_runs"] == 1
    assert table_counts["model_invocations"] == 1
    assert table_counts["mailbox_messages"] == 1
    assert table_counts["side_channel_events"] == 1
    assert table_counts["outbox_records"] == 1
    assert plan["stateFileCount"] == 2
    assert payload["operation"]["operationType"] == "deletion-plan"
    assert payload["operation"]["dryRun"] is True

    operations = client.get("/data-governance/operations").json()["operations"]
    assert operations[0]["scopeId"] == "task_data_governance_plan"
    assert operations[0]["status"] == "planned"


def test_running_task_delete_is_blocked_and_audited(monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_task_runtime_case(task_id="task_data_governance_running", status="running")
    backup_calls = 0

    def fake_backup(**_: object) -> dict[str, object]:
        nonlocal backup_calls
        backup_calls += 1
        return {"snapshotDir": "should-not-run"}

    monkeypatch.setattr("yggdrasil_core_api.services.data_governance_service.create_runtime_backup", fake_backup)

    response = client.post(
        "/data-governance/delete",
        json={
            "scopeKind": "task",
            "scopeId": "task_data_governance_running",
            "confirmScopeId": "task_data_governance_running",
            "backupBeforeDelete": True,
            "reason": "test blocked delete",
        },
    )

    assert response.status_code == 409
    assert "running" in response.json()["detail"]
    assert backup_calls == 0
    assert _row_count(TaskORM, TaskORM.id == "task_data_governance_running") == 1
    operations = client.get("/data-governance/operations").json()["operations"]
    assert operations[0]["operationType"] == "delete"
    assert operations[0]["status"] == "blocked"


def test_completed_task_delete_removes_runtime_children_and_state_files(monkeypatch: pytest.MonkeyPatch) -> None:
    request_path, response_path = _seed_task_runtime_case(task_id="task_data_governance_delete", status="completed")
    monkeypatch.setattr(
        "yggdrasil_core_api.services.data_governance_service.create_runtime_backup",
        lambda **_: {
            "name": "test-snapshot",
            "snapshotDir": "C:/tmp/yggdrasil-backups/test-snapshot",
            "createdAt": "2026-06-06T01:02:03Z",
            "databaseKind": "sqlite",
        },
    )

    response = client.post(
        "/data-governance/delete",
        json={
            "scopeKind": "task",
            "scopeId": "task_data_governance_delete",
            "confirmScopeId": "task_data_governance_delete",
            "includeStateFiles": True,
            "backupBeforeDelete": True,
            "reason": "test hard delete",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["result"]["status"] == "completed"
    assert payload["result"]["backup"]["snapshotDir"] == "C:/tmp/yggdrasil-backups/test-snapshot"
    certificate = payload["result"]["deletionCertificate"]
    assert certificate["scopeKind"] == "task"
    assert certificate["scopeId"] == "task_data_governance_delete"
    assert certificate["deletedRows"] >= 1
    assert certificate["stateFiles"]["deleted"] == 2
    assert certificate["backupSnapshotDir"] == "C:/tmp/yggdrasil-backups/test-snapshot"
    assert payload["operation"]["status"] == "completed"
    assert _row_count(TaskORM, TaskORM.id == "task_data_governance_delete") == 0
    assert _row_count(AgentRunORM, AgentRunORM.task_id == "task_data_governance_delete") == 0
    assert _row_count(ModelInvocationORM, ModelInvocationORM.task_id == "task_data_governance_delete") == 0
    assert _row_count(ModelRouteDecisionORM, ModelRouteDecisionORM.task_id == "task_data_governance_delete") == 0
    assert _row_count(MailboxMessageORM, MailboxMessageORM.task_id == "task_data_governance_delete") == 0
    assert _row_count(SideChannelEventORM, SideChannelEventORM.task_id == "task_data_governance_delete") == 0
    assert _row_count(OutboxRecordORM, OutboxRecordORM.aggregate_id == "task_data_governance_delete") == 0
    assert not Path(request_path).exists()
    assert not Path(response_path).exists()
