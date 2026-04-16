from fastapi import APIRouter, Depends, Query

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/summary")
def get_observability_summary(
    limit: int = Query(default=60, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.get_observability_summary(limit=limit)