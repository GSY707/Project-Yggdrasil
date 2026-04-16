from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_nodes(
    branch_id: str | None = Query(default=None, alias="branchId"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_nodes(branch_id=branch_id, limit=limit)


@router.get("/{node_id}")
def get_node(node_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_node(node_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}") from exc


@router.post("", status_code=status.HTTP_201_CREATED)
def create_node(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.create_node(payload)


@router.post("/{node_id}/versions", status_code=status.HTTP_201_CREATED)
def append_node_version(
    node_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.append_node_version(node_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}") from exc


@router.post("/{node_id}/annotations", status_code=status.HTTP_201_CREATED)
def add_node_annotation(
    node_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.add_node_annotation(node_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Node not found: {node_id}") from exc