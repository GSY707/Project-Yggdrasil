from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, status

from yggdrasil_sdk.persistence.coordination import RedisCoordinator

from .runtime import build_root_mount_package, load_package_entry, prepare_pause_snapshot, queue_main_agent_execution, request_task_pause
from yggdrasil_sdk import get_persistence_runtime


app = FastAPI(title="Yggdrasil Agent Runtime", version="0.1.0")


@app.get("/health")
def healthcheck() -> dict[str, object]:
    runtime = get_persistence_runtime()
    coordinator = RedisCoordinator(runtime.settings)
    return {
        "status": "ok",
        "service": "agent-runtime",
        "database": runtime.ping_database(),
        "redis": coordinator.ping(),
    }


@app.get("/runtime/root-mount/{task_id}")
def root_mount_preview(
    task_id: str,
    task_objective: str | None = None,
    current_focus: str | None = None,
    resume_message: str | None = None,
) -> dict[str, object]:
    return build_root_mount_package(
        task_id,
        {
            "taskObjective": task_objective,
            "currentFocus": current_focus,
            "resumeMessage": resume_message,
        },
    )


@app.post("/runtime/pause/{task_id}")
def pause_preview(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    return prepare_pause_snapshot(task_id, payload)


@app.post("/runtime/tasks/{task_id}/start", status_code=status.HTTP_202_ACCEPTED)
def start_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        request = dict(payload or {})
        request["command"] = "start"
        return queue_main_agent_execution(task_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/pause-request", status_code=status.HTTP_202_ACCEPTED)
def pause_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return request_task_pause(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/resume", status_code=status.HTTP_202_ACCEPTED)
def resume_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        request = dict(payload or {})
        request["command"] = "resume"
        return queue_main_agent_execution(task_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.get("/runtime/package-entry")
def get_package_entry(locator: str = Query(..., min_length=1)) -> dict[str, object]:
    payload = load_package_entry(locator)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Package entry not found: {locator}")
    return {"locator": locator, "payload": payload}