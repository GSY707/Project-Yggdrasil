from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/dataset-versions")
def list_dataset_versions(
    dataset_name: str | None = Query(default=None, alias="datasetName"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_dataset_versions(dataset_name=dataset_name, limit=limit)


@router.get("/dataset-versions/{dataset_version_id}")
def get_dataset_version(
    dataset_version_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.get_dataset_version(dataset_version_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset version not found: {dataset_version_id}") from exc


@router.post("/dataset-versions/prepare", status_code=status.HTTP_201_CREATED)
def prepare_dataset_version(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.prepare_dataset_version(payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/model-artifacts")
def list_model_artifacts(
    dataset_version_id: str | None = Query(default=None, alias="datasetVersionId"),
    status_value: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_model_artifacts(dataset_version_id=dataset_version_id, status=status_value, limit=limit)


@router.get("/model-artifacts/{artifact_id}")
def get_model_artifact(artifact_id: str, service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    try:
        return service.get_model_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model artifact not found: {artifact_id}") from exc


@router.post("/model-artifacts/stage", status_code=status.HTTP_201_CREATED)
def stage_model_artifact(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.stage_model_artifact(payload)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc