from fastapi import APIRouter, Depends

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/health")
def healthcheck(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.health_report()