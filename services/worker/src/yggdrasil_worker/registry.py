from __future__ import annotations

import json
import os
import signal
from typing import Any

from yggdrasil_sdk import get_persistence_runtime, observe_span, record_log, record_metric, sync_module_catalog_snapshot
from yggdrasil_sdk.catalog import load_in_process_plugin
from yggdrasil_sdk.collaboration_runtime import execute_subagent_work_item
from yggdrasil_sdk.contracts import WorkerActivityDescriptor
from yggdrasil_sdk.hooks import HookNames
from yggdrasil_sdk.persistence.coordination import RedisCoordinator
from yggdrasil_sdk.runtime_kernel import AGENT_RUNTIME_QUEUE, execute_main_agent_work_item
from yggdrasil_sdk.support import utc_now
from yggdrasil_sdk.runtime_kernel.shutdown_control import request_shutdown


def _handle_shutdown_signal(signum: int, frame: object) -> None:
    """Handle SIGTERM/SIGINT by requesting a graceful shutdown."""
    request_shutdown()


def _register_shutdown_handlers() -> None:
    """Register OS signal handlers for graceful shutdown (only in main thread)."""
    import threading
    if threading.current_thread() is not threading.main_thread():
        return
    try:
        signal.signal(signal.SIGTERM, _handle_shutdown_signal)
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
    except (OSError, ValueError):
        pass  # Not in main thread or signals unavailable on this platform


_register_shutdown_handlers()


CORE_ACTIVITIES = (
    WorkerActivityDescriptor(
        name="core.agent.main.execute",
        moduleId="kernel",
        description="Execute the main agent lifecycle step with route decision, write flush, safe-stop, and resume handling.",
        implementationRef="yggdrasil_worker.registry:core.agent.main.execute",
        timeoutMs=60000,
        retryable=True,
    ),
    WorkerActivityDescriptor(
        name="core.agent.subagent.execute",
        moduleId="kernel",
        description="Execute a sub-agent branch run, publish its readonly-context result, and open a pull request.",
        implementationRef="yggdrasil_worker.registry:core.agent.subagent.execute",
        timeoutMs=90000,
        retryable=True,
    ),
    WorkerActivityDescriptor(
        name="core.memory.import.materialize",
        moduleId="kernel",
        description="Materialize accepted import plans into durable node and edge writes.",
        implementationRef="yggdrasil_worker.registry:core.memory.import.materialize",
        timeoutMs=30000,
        retryable=True,
    ),
    WorkerActivityDescriptor(
        name="core.context.pruning.verify",
        moduleId="kernel",
        description="Verify protected refs survive context pruning before resuming execution.",
        implementationRef="yggdrasil_worker.registry:core.context.pruning.verify",
        timeoutMs=15000,
        retryable=True,
    ),
    WorkerActivityDescriptor(
        name="core.module.health.snapshot",
        moduleId="kernel",
        description="Refresh the current module health snapshot and publish it for operators.",
        implementationRef="yggdrasil_worker.registry:core.module.health.snapshot",
        timeoutMs=10000,
        retryable=True,
    ),
)


def _normalize_activity(activity: Any, module_id: str) -> WorkerActivityDescriptor:
    if isinstance(activity, WorkerActivityDescriptor):
        return activity
    if not isinstance(activity, dict):
        return WorkerActivityDescriptor(
            name=str(activity),
            moduleId=module_id,
            description=f"Worker activity exported by {module_id}.",
            implementationRef=str(activity),
            timeoutMs=3000,
            retryable=True,
        )
    return WorkerActivityDescriptor(
        name=str(activity.get("name")),
        moduleId=str(activity.get("moduleId", module_id)),
        description=str(activity.get("description", f"Worker activity exported by {module_id}.")),
        implementationRef=str(activity.get("implementationRef", activity.get("name"))),
        timeoutMs=int(activity.get("timeoutMs", 3000)),
        retryable=bool(activity.get("retryable", True)),
    )


def discover_worker_activities() -> list[WorkerActivityDescriptor]:
    snapshot = sync_module_catalog_snapshot()
    installs_by_module_id = {record.module_id: record for record in snapshot.installs}
    activities: list[WorkerActivityDescriptor] = list(CORE_ACTIVITIES)

    for manifest in snapshot.manifests:
        install = installs_by_module_id[manifest.module_id]
        if install.desired_state != "enabled" or install.lifecycle_state not in {"active", "degraded"}:
            continue
        if HookNames.WORKER_ACTIVITIES_REGISTER not in manifest.hooks or not manifest.entry_point:
            continue

        plugin = load_in_process_plugin(manifest.entry_point)
        for registration in plugin.register_hooks():
            if registration.name != HookNames.WORKER_ACTIVITIES_REGISTER:
                continue
            result = registration.handler(
                {
                    "moduleId": manifest.module_id,
                    "manifest": manifest.model_dump(by_alias=True),
                    "generatedAt": utc_now().isoformat(),
                }
            )
            if not isinstance(result, dict):
                continue
            for activity in result.get("activities", []):
                activities.append(_normalize_activity(activity, manifest.module_id))

    deduplicated = {activity.name: activity for activity in activities}
    return [deduplicated[name] for name in sorted(deduplicated)]


def build_worker_report() -> dict[str, object]:
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    activities = discover_worker_activities()
    return {
        "generatedAt": utc_now().isoformat(),
        "database": runtime.ping_database(),
        "redis": coordinator.ping(),
        "totalActivities": len(activities),
        "modules": sorted({activity.module_id for activity in activities}),
        "workKinds": [activity.name for activity in activities],
        "activities": [activity.model_dump(by_alias=True) for activity in activities],
    }


def enqueue_work_item(queue: str, payload: dict[str, Any]) -> dict[str, object]:
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    try:
        queue_depth = coordinator.enqueue_job(queue, payload)
    except Exception as exc:
        return {
            "status": "error",
            "queue": queue,
            "detail": str(exc),
            "payload": payload,
        }
    return {
        "status": "enqueued",
        "queue": queue,
        "queueDepth": queue_depth,
        "payload": payload,
    }


def pop_work_item(queue: str, timeout_seconds: int = 1) -> dict[str, object]:
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    try:
        payload = coordinator.pop_job(queue, timeout_seconds=timeout_seconds)
    except Exception as exc:
        return {
            "status": "error",
            "queue": queue,
            "detail": str(exc),
            "payload": None,
        }
    return {
        "status": "received" if payload is not None else "empty",
        "queue": queue,
        "payload": payload,
    }


def dispatch_work_item(payload: dict[str, Any]) -> dict[str, object]:
    activity = str(payload.get("activity") or "")
    if activity == "core.agent.main.execute":
        return execute_main_agent_work_item(payload)
    if activity == "core.agent.subagent.execute":
        return execute_subagent_work_item(payload)
    return {
        "status": "ignored",
        "activity": activity,
        "detail": f"Unsupported activity: {activity}",
    }


def run_worker_once(queue: str = AGENT_RUNTIME_QUEUE, timeout_seconds: int = 0) -> dict[str, object]:
    with observe_span("worker", f"queue:{queue}", kind="worker", attributes={"queue": queue}) as span:
        popped = pop_work_item(queue, timeout_seconds=timeout_seconds)
        span["attributes"]["popStatus"] = popped["status"]
        if popped["status"] != "received":
            return popped
        payload = popped["payload"]
        if not isinstance(payload, dict):
            record_log(
                "worker",
                "error",
                "Worker payload must be a JSON object.",
                attributes={"queue": queue, "traceId": span["traceId"], "payload": json.dumps(payload, ensure_ascii=False)},
            )
            return {
                "status": "error",
                "queue": queue,
                "detail": "Worker payload must be a JSON object.",
                "payload": payload,
            }
        span["attributes"]["activity"] = str(payload.get("activity") or "")
        result = dispatch_work_item(payload)
        worker_status = "processed" if result.get("status") not in {"error"} else "error"
        record_metric(
            "worker",
            "work-item.processed",
            1,
            kind="counter",
            attributes={"queue": queue, "activity": str(payload.get("activity") or "unknown"), "status": worker_status},
        )
        if worker_status == "error":
            record_log(
                "worker",
                "error",
                "Worker activity failed.",
                attributes={"queue": queue, "traceId": span["traceId"], "payload": payload, "result": result},
            )
        return {
            "status": worker_status,
            "queue": queue,
            "payload": payload,
            "result": result,
        }


def drain_work_queue(queue: str = AGENT_RUNTIME_QUEUE, *, max_items: int = 10, timeout_seconds: int = 1) -> dict[str, object]:
    processed: list[dict[str, object]] = []
    for _ in range(max_items):
        result = run_worker_once(queue, timeout_seconds=timeout_seconds)
        processed.append(result)
        if result["status"] in {"empty", "error"}:
            break
    return {
        "status": "drained",
        "queue": queue,
        "processed": processed,
        "processedCount": sum(1 for item in processed if item.get("status") == "processed"),
    }