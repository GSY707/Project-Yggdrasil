from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/prompt-profiles")
def list_prompt_profiles(
    app_id: str | None = Query(default=None, alias="appId"),
    active_capabilities: str | None = Query(default=None, alias="activeCapabilities"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    capability_list = [item.strip() for item in (active_capabilities or "").split(",") if item.strip()]
    return service.list_prompt_profiles(app_id=app_id, active_capabilities=capability_list or None)


@router.get("/seed-templates")
def list_seed_templates(
    app_id: str | None = Query(default=None, alias="appId"),
    active_capabilities: str | None = Query(default=None, alias="activeCapabilities"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    capability_list = [item.strip() for item in (active_capabilities or "").split(",") if item.strip()]
    return service.list_seed_templates(app_id=app_id, active_capabilities=capability_list or None)


@router.get("/registered-tools")
def list_registered_tools(
    app_id: str | None = Query(default=None, alias="appId"),
    active_capabilities: str | None = Query(default=None, alias="activeCapabilities"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    capability_list = [item.strip() for item in (active_capabilities or "").split(",") if item.strip()]
    return service.list_registered_prompt_tools(active_capabilities=capability_list or None, app_id=app_id)


@router.get("/compile-artifacts")
def list_prompt_compile_artifacts(
    project_id: str | None = Query(default=None, alias="projectId"),
    task_id: str | None = Query(default=None, alias="taskId"),
    app_id: str | None = Query(default=None, alias="appId"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_prompt_compile_artifacts(project_id=project_id, task_id=task_id, app_id=app_id, limit=limit)


@router.get("/compile-artifacts/{artifact_id}")
def get_prompt_compile_artifact(
    artifact_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.get_prompt_compile_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Prompt compile artifact not found: {artifact_id}") from exc


@router.post("/compile-preview", status_code=status.HTTP_201_CREATED)
def compile_prompt_preview(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.compile_prompt_preview(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc