from __future__ import annotations

from collections import defaultdict

from fastapi.testclient import TestClient

from yggdrasil_module_host.app import app as module_host_app
from yggdrasil_sdk import EventEnvelope, HookNames, ModulePlatformService, new_id, utc_now


class FakeEventBus:
    def __init__(self) -> None:
        self.queued: dict[str, list[EventEnvelope]] = defaultdict(list)
        self.published: list[EventEnvelope] = []

    def enqueue(self, envelope: EventEnvelope) -> None:
        self.queued[envelope.event_type].append(envelope)

    def ping(self) -> dict[str, object]:
        return {"status": "ok", "backend": "fake"}

    def ensure_stream(self) -> dict[str, object]:
        return {"status": "ok", "stream": "fake"}

    def publish(self, envelope: EventEnvelope) -> dict[str, object]:
        self.published.append(envelope)
        return {"status": "published", "eventId": envelope.event_id}

    def consume(
        self,
        *,
        event_type: str,
        consumer_group: str,
        batch: int,
        timeout_seconds: int,
        handler,
    ) -> dict[str, object]:
        queued = self.queued.get(event_type, [])
        selected = queued[:batch]
        self.queued[event_type] = queued[batch:]
        acked = 0
        nacked = 0
        for envelope in selected:
            if handler(envelope):
                acked += 1
            else:
                nacked += 1
        return {
            "status": "ok",
            "consumerGroup": consumer_group,
            "timeoutSeconds": timeout_seconds,
            "fetched": len(selected),
            "acked": acked,
            "nacked": nacked,
            "errors": [],
        }


def test_module_platform_reconciles_registry_runtime_state() -> None:
    service = ModulePlatformService(event_bus=FakeEventBus())
    snapshot = service.sync_catalog()

    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    assert installs_by_module_id["text-memory"].lifecycle_state == "active"
    assert installs_by_module_id["context-pruning"].lifecycle_state == "active"
    assert installs_by_module_id["subagent-pr"].lifecycle_state == "active"
    assert installs_by_module_id["shared-memory"].lifecycle_state == "active"
    assert installs_by_module_id["pause-resume"].lifecycle_state == "active"
    assert installs_by_module_id["multimodal-memory"].lifecycle_state == "active"
    assert installs_by_module_id["memory-organizer"].lifecycle_state == "active"
    assert installs_by_module_id["relation-discovery"].lifecycle_state == "active"
    assert installs_by_module_id["training-lab"].lifecycle_state == "active"
    assert installs_by_module_id["scene-learning-coach"].lifecycle_state == "active"
    assert installs_by_module_id["scene-scenic-guide"].lifecycle_state == "active"

    hook_names = {hook.hook_name for hook in snapshot.hooks}
    assert HookNames.MODULE_ENABLE_PREFLIGHT in hook_names
    assert HookNames.MODULE_HEALTH_REPORT in hook_names
    assert HookNames.AGENT_STARTUP_MOUNT_ROOT in hook_names
    assert HookNames.TASK_PAUSE_PREPARE in hook_names
    assert HookNames.MEMORY_RETRIEVE_RERANK in hook_names

    subscriptions = {(record.event_type, record.status) for record in snapshot.subscriptions}
    assert ("import.accepted", "active") in subscriptions
    assert ("context.pruning.requested", "active") in subscriptions
    assert ("task.started", "active") in subscriptions

    config_bindings = service.list_config_bindings()["configBindings"]
    assert {record["moduleId"] for record in config_bindings} >= {
        "text-memory",
        "context-pruning",
        "subagent-pr",
        "shared-memory",
        "pause-resume",
        "multimodal-memory",
        "memory-organizer",
        "relation-discovery",
        "training-lab",
        "scene-learning-coach",
        "scene-scenic-guide",
    }

    health_reports = service.list_health_reports()["health"]
    health_by_module_id = {record["moduleId"]: record for record in health_reports}
    assert health_by_module_id["text-memory"]["status"] == "healthy"
    assert health_by_module_id["subagent-pr"]["status"] == "healthy"
    assert health_by_module_id["shared-memory"]["status"] == "healthy"
    assert health_by_module_id["training-lab"]["status"] == "healthy"
    assert health_by_module_id["scene-learning-coach"]["status"] == "healthy"
    assert health_by_module_id["scene-scenic-guide"]["status"] == "healthy"


def test_module_platform_consumes_events_and_publishes_outbox() -> None:
    event_bus = FakeEventBus()
    service = ModulePlatformService(event_bus=event_bus)
    service.sync_catalog()
    service.publish_pending_events(limit=100)
    event_bus.published.clear()

    event_bus.enqueue(
        EventEnvelope(
            eventType="import.accepted",
            eventVersion=1,
            eventId=new_id("evt", "import.accepted", stable=True),
            occurredAt=utc_now(),
            source="tests",
            projectId="project_default",
            spaceId="space_default",
            branchId="branch_main",
            taskId="task_import_1",
            correlationId="corr_import_1",
            schemaRef="yggdrasil://events/import.accepted/v1",
            payload={
                "importJob": {"id": "import_job_1", "projectId": "project_default", "spaceId": "space_default", "branchId": "branch_main"},
                "orderedFragments": [
                    {"id": "fragment_1", "text": "世界树计划需要将长期目标与当前任务统一成知识节点。"},
                    {"id": "fragment_2", "text": "上下文恢复与任务执行需要共享结构化记忆。"},
                ],
            },
        )
    )

    consume_result = service.consume_events(module_id="text-memory", limit=1, timeout_seconds=1)
    assert consume_result["handled"] == 1
    assert consume_result["failed"] == 0
    assert consume_result["emitted"] == 1

    publish_result = service.publish_pending_events(limit=20)
    assert publish_result["published"] >= 1
    assert any(envelope.event_type == "memory.tree.plan.proposed" for envelope in event_bus.published)


def test_module_host_api_exposes_m3_control_plane() -> None:
    client = TestClient(module_host_app)

    reconcile = client.post("/modules/reconcile")
    assert reconcile.status_code == 200
    assert reconcile.json()["status"] == "synced"

    hooks = client.get("/hooks")
    assert hooks.status_code == 200
    assert any(record["hookName"] == HookNames.MODULE_ENABLE_PREFLIGHT for record in hooks.json()["hooks"])

    subscriptions = client.get("/subscriptions")
    assert subscriptions.status_code == 200
    assert any(record["eventType"] == "import.accepted" for record in subscriptions.json()["subscriptions"])

    config_bindings = client.get("/config-bindings")
    assert config_bindings.status_code == 200
    assert any(record["moduleId"] == "text-memory" for record in config_bindings.json()["configBindings"])

    disabled = client.post("/modules/text-memory/disable")
    assert disabled.status_code == 200
    assert disabled.json()["module"]["install"]["desiredState"] == "disabled"

    enabled = client.post("/modules/text-memory/enable")
    assert enabled.status_code == 200
    assert enabled.json()["module"]["install"]["desiredState"] == "enabled"