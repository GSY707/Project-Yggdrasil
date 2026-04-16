from fastapi import APIRouter, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/suites")
def list_evaluation_suites(service: WorkspaceService = Depends(get_workspace_service)) -> dict[str, object]:
    return service.list_evaluation_suites()


@router.get("/runs")
def list_evaluation_runs(
    suite_id: str | None = Query(default=None, alias="suiteId"),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_evaluation_runs(suite_id=suite_id, status=status_filter, limit=limit)


@router.post("/suites/{suite_id}/run", status_code=status.HTTP_201_CREATED)
def execute_evaluation_suite(
    suite_id: str,
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.execute_evaluation_suite(suite_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Evaluation suite not found: {suite_id}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc