from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/manifest")
def get_data_governance_manifest(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.get_data_governance_manifest()


@router.get("/operations")
def list_data_governance_operations(
    limit: int = Query(default=50, ge=1, le=200),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_data_governance_operations(limit=limit)


@router.post("/deletion-plan")
def create_deletion_plan(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_deletion_plan(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scope object not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/delete")
def execute_delete(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.execute_deletion_request(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Scope object not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
