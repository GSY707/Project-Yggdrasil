from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/import-jobs")
def list_import_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_import_jobs(status=status_filter, limit=limit)


@router.get("/import-jobs/{import_job_id}")
def get_import_job(import_job_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_import_job(import_job_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import job not found: {import_job_id}") from exc


@router.post("/import-jobs", status_code=status.HTTP_201_CREATED)
def create_import_job(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_import_job(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/import-jobs/{import_job_id}/process")
def process_import_job(
    import_job_id: str,
    payload: dict[str, Any] = Body(default={}),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.process_import_job(import_job_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Import job not found: {import_job_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/retrievals", status_code=status.HTTP_201_CREATED)
def create_retrieval(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_retrieval(payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc