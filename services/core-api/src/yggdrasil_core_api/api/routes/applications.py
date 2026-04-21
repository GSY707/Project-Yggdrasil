from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_applications(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.list_applications()


@router.get("/{app_id}")
def get_application(
    app_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.get_application(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application not found: {app_id}") from exc


@router.post("/{app_id}/activate", status_code=status.HTTP_200_OK)
def activate_application(
    app_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.activate_application(app_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application not found: {app_id}") from exc


@router.post("/{app_id}/config", status_code=status.HTTP_200_OK)
def update_application_config(
    app_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.update_application_config(app_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Application not found: {app_id}") from exc