from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/route-decisions")
def list_route_decisions(
    task_id: str | None = Query(default=None, alias="taskId"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_route_decisions(task_id=task_id, limit=limit)


@router.post("/route-decisions", status_code=status.HTTP_201_CREATED)
def create_route_decision(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_route_decision(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc