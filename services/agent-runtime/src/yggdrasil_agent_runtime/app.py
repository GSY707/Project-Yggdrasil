from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, status

from yggdrasil_sdk import instrument_fastapi_app
from yggdrasil_sdk.persistence.coordination import RedisCoordinator

from .runtime import approve_task_completion, build_root_mount_package, cancel_task_execution, create_task_branch_from_snapshot, load_package_entry, pause_task_execution, prepare_pause_snapshot, queue_main_agent_execution, request_task_revision, retry_task_execution, save_current_task_snapshot
from yggdrasil_sdk import get_persistence_runtime


app = FastAPI(title="Yggdrasil Agent Runtime", version="0.1.0")
instrument_fastapi_app(app, "agent-runtime")


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


@app.post("/runtime/tasks/{task_id}/pause", status_code=status.HTTP_202_ACCEPTED)
def pause_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return pause_task_execution(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


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


@app.post("/runtime/tasks/{task_id}/retry", status_code=status.HTTP_202_ACCEPTED)
def retry_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return retry_task_execution(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
def cancel_task(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return cancel_task_execution(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/snapshots/save-current", status_code=status.HTTP_201_CREATED)
def save_current_snapshot(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return save_current_task_snapshot(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/branches", status_code=status.HTTP_201_CREATED)
def create_task_branch(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return create_task_branch_from_snapshot(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/approve-completion")
def approve_runtime_task_completion(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return approve_task_completion(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@app.post("/runtime/tasks/{task_id}/request-revision", status_code=status.HTTP_202_ACCEPTED)
def request_runtime_task_revision(task_id: str, payload: dict[str, Any] | None = Body(default=None)) -> dict[str, object]:
    try:
        return request_task_revision(task_id, payload)
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
