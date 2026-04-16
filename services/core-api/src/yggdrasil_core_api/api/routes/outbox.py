from fastapi import APIRouter, Depends, Query

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("")
def list_outbox(
    publish_status: str | None = Query(default=None, alias="publishStatus"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_outbox(publish_status=publish_status, limit=limit)