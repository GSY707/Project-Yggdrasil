from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_tasks(status=status_filter, limit=limit)


@router.get("/{task_id}")
def get_task(task_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task not found: {task_id}") from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.create_task(payload)


@router.post("/{task_id}/runs", status_code=status.HTTP_201_CREATED)
def create_agent_run(
    task_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_agent_run(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task not found: {task_id}") from exc


@router.get("/{task_id}/snapshots")
def list_task_snapshots(
    task_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_task_snapshots(task_id)