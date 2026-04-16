from fastapi import APIRouter, Depends

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/overview")
def get_workbench_overview(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.get_workbench_overview()