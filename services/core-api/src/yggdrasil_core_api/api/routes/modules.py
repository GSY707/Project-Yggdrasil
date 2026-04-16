from fastapi import APIRouter, Depends

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_modules(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.list_modules()