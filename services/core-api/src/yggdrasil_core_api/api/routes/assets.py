from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_assets(
    project_id: str | None = Query(default=None, alias="projectId"),
    space_id: str | None = Query(default=None, alias="spaceId"),
    branch_id: str | None = Query(default=None, alias="branchId"),
    owner_node_id: str | None = Query(default=None, alias="ownerNodeId"),
    media_type: str | None = Query(default=None, alias="mediaType"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_assets(
        project_id=project_id,
        space_id=space_id,
        branch_id=branch_id,
        owner_node_id=owner_node_id,
        media_type=media_type,
        limit=limit,
    )


@router.get("/{asset_id}")
def get_asset(asset_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_asset(asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset not found: {asset_id}") from exc


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
def ingest_asset(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.ingest_asset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc