from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def get_mcp_bridge_state(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.get_mcp_bridge_state()


@router.post("/imports/refresh", status_code=status.HTTP_200_OK)
def refresh_mcp_bridge_imports(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.refresh_mcp_bridge_imports()


@router.post("/sync", status_code=status.HTTP_200_OK)
def sync_mcp_bridge(
    payload: dict[str, Any] = Body(default={}),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.sync_mcp_bridge(payload)


@router.post("/workspace", status_code=status.HTTP_200_OK)
def update_mcp_bridge_workspace(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.update_mcp_bridge_workspace(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers", status_code=status.HTTP_200_OK)
def upsert_mcp_bridge_server(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.upsert_mcp_bridge_server(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/servers/{server_id}/enable", status_code=status.HTTP_200_OK)
def enable_mcp_bridge_server(
    server_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.set_mcp_bridge_server_enabled(server_id, enabled=True)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server not found: {server_id}") from exc


@router.post("/servers/{server_id}/disable", status_code=status.HTTP_200_OK)
def disable_mcp_bridge_server(
    server_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.set_mcp_bridge_server_enabled(server_id, enabled=False)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server not found: {server_id}") from exc


@router.post("/servers/{server_id}/sync", status_code=status.HTTP_200_OK)
def sync_mcp_bridge_server(
    server_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.sync_mcp_bridge({"serverIds": [server_id]})
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"MCP server not found: {server_id}") from exc