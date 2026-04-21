from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/spaces")
def list_spaces(
    project_id: str | None = Query(default=None, alias="projectId"),
    space_type: str | None = Query(default=None, alias="spaceType"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_spaces(project_id=project_id, space_type=space_type, status=status_filter, limit=limit)


@router.post("/spaces", status_code=status.HTTP_201_CREATED)
def create_space(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_space(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/branches")
def list_branches(
    project_id: str | None = Query(default=None, alias="projectId"),
    space_id: str | None = Query(default=None, alias="spaceId"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_branches(project_id=project_id, space_id=space_id, status=status_filter, limit=limit)


@router.post("/branches", status_code=status.HTTP_201_CREATED)
def create_branch(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_branch(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project or space not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/space-mounts")
def list_space_mounts(
    project_id: str | None = Query(default=None, alias="projectId"),
    host_space_id: str | None = Query(default=None, alias="hostSpaceId"),
    mounted_space_id: str | None = Query(default=None, alias="mountedSpaceId"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_space_mounts(
        project_id=project_id,
        host_space_id=host_space_id,
        mounted_space_id=mounted_space_id,
        status=status_filter,
        limit=limit,
    )


@router.post("/space-mounts", status_code=status.HTTP_201_CREATED)
def create_space_mount(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_space_mount(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project or space not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/permission-tuples")
def list_permission_tuples(
    project_id: str | None = Query(default=None, alias="projectId"),
    subject: str | None = Query(default=None),
    relation: str | None = Query(default=None),
    resource: str | None = Query(default=None),
    effect: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_permission_tuples(
        project_id=project_id,
        subject=subject,
        relation=relation,
        resource=resource,
        effect=effect,
        limit=limit,
    )


@router.post("/permission-tuples", status_code=status.HTTP_201_CREATED)
def create_permission_tuple(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_permission_tuple(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Project not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.get("/pull-requests")
def list_pull_requests(
    project_id: str | None = Query(default=None, alias="projectId"),
    source_branch_id: str | None = Query(default=None, alias="sourceBranchId"),
    target_branch_id: str | None = Query(default=None, alias="targetBranchId"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_pull_requests(
        project_id=project_id,
        source_branch_id=source_branch_id,
        target_branch_id=target_branch_id,
        status=status_filter,
        limit=limit,
    )


@router.get("/pull-requests/{pr_id}")
def get_pull_request(pr_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_pull_request(pr_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pull request not found: {pr_id}") from exc


@router.post("/subagents/{parent_task_id}/launch", status_code=status.HTTP_201_CREATED)
def launch_subagent(
    parent_task_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.launch_subagent(parent_task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Task or branch not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/pull-requests", status_code=status.HTTP_201_CREATED)
def create_pull_request(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_pull_request(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Branch not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post("/pull-requests/{pr_id}/review")
def review_pull_request(
    pr_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.review_pull_request(pr_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pull request not found: {exc}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc