from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status

from ...services import WorkspaceService, get_workspace_service


router = APIRouter()


@router.get("/route-decisions")
def list_route_decisions(
    task_id: str | None = Query(default=None, alias="taskId"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_route_decisions(task_id=task_id, limit=limit)


@router.post("/route-decisions", status_code=status.HTTP_201_CREATED)
def create_route_decision(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.create_route_decision(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/model-invocations")
def list_model_invocations(
    task_id: str | None = Query(default=None, alias="taskId"),
    agent_run_id: str | None = Query(default=None, alias="agentRunId"),
    app_id: str | None = Query(default=None, alias="appId"),
    status_value: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    return service.list_model_invocations(
        task_id=task_id,
        agent_run_id=agent_run_id,
        app_id=app_id,
        status=status_value,
        limit=limit,
    )


@router.post("/analysis/runs")
def analyze_llm_work_run_view(
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.analyze_llm_work(payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/analysis/runs/{analysis_id}")
def get_llm_work_analysis(
    analysis_id: str,
    granularity: str | None = Query(default=None, alias="granularity"),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.get_llm_work_analysis(analysis_id, granularity=granularity)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/mailbox")
def list_task_mailbox_messages(
    task_id: str,
    status_value: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.list_task_mailbox_messages(task_id, status=status_value, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/mailbox", status_code=status.HTTP_201_CREATED)
def post_task_mailbox_message(
    task_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.post_task_mailbox_message(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/side-channel")
def list_task_side_channel_events(
    task_id: str,
    agent_run_id: str | None = Query(default=None, alias="agentRunId"),
    level: str | None = Query(default=None, alias="level"),
    limit: int = Query(default=100, ge=1, le=500),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.list_task_side_channel_events(task_id, agent_run_id=agent_run_id, level=level, limit=limit)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/side-channel", status_code=status.HTTP_201_CREATED)
def post_task_side_channel_event(
    task_id: str,
    payload: dict[str, Any] = Body(...),
    service: WorkspaceService = Depends(get_workspace_service),
) -> dict[str, object]:
    try:
        return service.post_task_side_channel_event(task_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc