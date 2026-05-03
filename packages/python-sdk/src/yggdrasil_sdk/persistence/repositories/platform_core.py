from ._common import *  # noqa: F403,F401

class WorkspaceBootstrapRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def ensure_default_workspace(self) -> dict[str, str]:
        now = utc_now()
        system_actor = _actor(None)
        project_created = False
        space_created = False

        project = self.session.get(ProjectORM, DEFAULT_PROJECT_ID)
        if project is None:
            project = ProjectORM(
                id=DEFAULT_PROJECT_ID,
                display_name="Project Yggdrasil",
                status="active",
                export_policy="project-package-only",
                created_at=now,
                created_by=system_actor.model_dump(mode="json"),
            )
            self.session.add(project)
            project_created = True

        if project_created:
            self.session.flush()

        space = self.session.get(SpaceORM, DEFAULT_SPACE_ID)
        if space is None:
            space = SpaceORM(
                id=DEFAULT_SPACE_ID,
                project_id=DEFAULT_PROJECT_ID,
                space_type="default",
                status="active",
                owner_subject=None,
                created_at=now,
            )
            self.session.add(space)
            space_created = True

        if space_created:
            self.session.flush()

        branch = self.session.get(MemoryBranchORM, DEFAULT_BRANCH_ID)
        if branch is None:
            branch = MemoryBranchORM(
                id=DEFAULT_BRANCH_ID,
                project_id=DEFAULT_PROJECT_ID,
                space_id=DEFAULT_SPACE_ID,
                name="main",
                base_branch_id=None,
                head_ref=None,
                status="active",
                created_at=now,
                created_by=system_actor.model_dump(mode="json"),
            )
            self.session.add(branch)

        self.session.flush()
        return _ensure_branch_roots(
            self.session,
            project_id=DEFAULT_PROJECT_ID,
            space_id=DEFAULT_SPACE_ID,
            branch_id=DEFAULT_BRANCH_ID,
            created_by=system_actor,
            now=now,
        )

    def ensure_branch_workspace(
        self,
        *,
        branch_id: str,
        project_id: str = DEFAULT_PROJECT_ID,
        space_id: str = DEFAULT_SPACE_ID,
        branch_name: str | None = None,
        base_branch_id: str | None = None,
        created_by: dict[str, Any] | ActorRef | None = None,
    ) -> dict[str, str]:
        now = utc_now()
        actor = _actor(created_by)

        if project_id == DEFAULT_PROJECT_ID and space_id == DEFAULT_SPACE_ID:
            self.ensure_default_workspace()

        project = self.session.get(ProjectORM, project_id)
        if project is None:
            raise KeyError(f"Project {project_id} not found.")
        space = self.session.get(SpaceORM, space_id)
        if space is None:
            raise KeyError(f"Space {space_id} not found.")

        branch = self.session.get(MemoryBranchORM, branch_id)
        if branch is None:
            branch = MemoryBranchORM(
                id=branch_id,
                project_id=project_id,
                space_id=space_id,
                name=branch_name or branch_id,
                base_branch_id=base_branch_id,
                head_ref=None,
                status="active",
                created_at=now,
                created_by=actor.model_dump(mode="json"),
            )
            self.session.add(branch)
        else:
            if branch_name is not None:
                branch.name = branch_name
            if base_branch_id is not None:
                branch.base_branch_id = base_branch_id
            if branch.status == "deleted":
                branch.status = "active"

        self.session.flush()
        return _ensure_branch_roots(
            self.session,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            created_by=actor,
            now=now,
        )

class RuntimeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_model_route_decision(self, payload: dict[str, Any]) -> ModelRouteDecision:
        task_id = str(payload.get("taskId")) if payload.get("taskId") is not None else None
        agent_run_id = str(payload.get("agentRunId")) if payload.get("agentRunId") is not None else None
        if task_id is not None and self.session.get(TaskORM, task_id) is None:
            raise KeyError(f"Task {task_id} not found.")
        if agent_run_id is not None and self.session.get(AgentRunORM, agent_run_id) is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")
        candidate_models: list[dict[str, Any]] = []
        for candidate in payload.get("candidateModels") or []:
            if isinstance(candidate, dict):
                candidate_models.append(candidate)
            else:
                candidate_models.append({"model": str(candidate)})
        record = ModelRouteDecision(
            id=str(payload.get("id") or new_id("route", payload.get("taskId") or payload.get("selectedModel") or utc_now().isoformat())),
            taskId=task_id,
            agentRunId=agent_run_id,
            selectedModel=str(payload.get("selectedModel") or "gpt-5.4"),
            selectedProvider=str(payload.get("selectedProvider")) if payload.get("selectedProvider") is not None else None,
            candidateModels=candidate_models,
            reason=str(payload.get("reason") or "manual-route-decision"),
            budgetScore=float(payload.get("budgetScore", 0.5)),
            qualityScore=float(payload.get("qualityScore", 0.5)),
            latencyScore=float(payload.get("latencyScore", 0.5)),
            routePolicyVersion=str(payload.get("routePolicyVersion") or "v0.1-manual"),
            createdAt=utc_now(),
        )
        model = ModelRouteDecisionORM(
            id=record.id,
            task_id=record.task_id,
            agent_run_id=record.agent_run_id,
            selected_model=record.selected_model,
            selected_provider=record.selected_provider,
            candidate_models=list(record.candidate_models),
            reason=record.reason,
            budget_score=record.budget_score,
            quality_score=record.quality_score,
            latency_score=record.latency_score,
            route_policy_version=record.route_policy_version,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return record

    def list_model_route_decisions(self, *, task_id: str | None = None, limit: int = 100) -> list[ModelRouteDecision]:
        statement = sa.select(ModelRouteDecisionORM).order_by(ModelRouteDecisionORM.created_at.desc()).limit(limit)
        if task_id:
            statement = statement.where(ModelRouteDecisionORM.task_id == task_id)
        return [_route_decision_record(model) for model in self.session.execute(statement).scalars().all()]

    def create_model_invocation(self, payload: dict[str, Any]) -> ModelInvocationRecord:
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        task_id = str(payload.get("taskId")) if payload.get("taskId") is not None else None
        agent_run_id = str(payload.get("agentRunId")) if payload.get("agentRunId") is not None else None
        route_decision_id = str(payload.get("routeDecisionId")) if payload.get("routeDecisionId") is not None else None
        task = self.session.get(TaskORM, task_id) if task_id is not None else None
        run = self.session.get(AgentRunORM, agent_run_id) if agent_run_id is not None else None
        if self.session.get(ProjectORM, project_id) is None:
            raise KeyError(f"Project {project_id} not found.")
        if task_id is not None and task is None:
            raise KeyError(f"Task {task_id} not found.")
        if agent_run_id is not None and run is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")
        if route_decision_id is not None and self.session.get(ModelRouteDecisionORM, route_decision_id) is None:
            raise KeyError(f"Route decision {route_decision_id} not found.")
        if task is not None and run is not None and task.app_id != run.app_id:
            raise ValueError(f"Task {task_id} appId {task.app_id} does not match agent run {agent_run_id} appId {run.app_id}.")
        app_id = str(payload.get("appId") or (task.app_id if task is not None else None) or (run.app_id if run is not None else None) or DEFAULT_APP_ID)
        if task is not None and app_id != task.app_id:
            raise ValueError(f"Model invocation appId {app_id} does not match task {task_id} appId {task.app_id}.")
        if run is not None and app_id != run.app_id:
            raise ValueError(f"Model invocation appId {app_id} does not match agent run {agent_run_id} appId {run.app_id}.")

        record = ModelInvocationRecord(
            id=str(payload.get("id") or new_id("llm", agent_run_id or task_id or utc_now().isoformat())),
            appId=app_id,
            projectId=project_id,
            taskId=task_id,
            agentRunId=agent_run_id,
            routeDecisionId=route_decision_id,
            requestedModel=str(payload.get("requestedModel") or payload.get("selectedModel") or "unknown"),
            requestedProvider=str(payload.get("requestedProvider") or payload.get("selectedProvider")) if (payload.get("requestedProvider") or payload.get("selectedProvider")) is not None else None,
            resolvedModel=str(payload.get("resolvedModel") or payload.get("requestedModel") or payload.get("selectedModel") or "unknown"),
            resolvedProvider=str(payload.get("resolvedProvider") or payload.get("requestedProvider") or payload.get("selectedProvider")) if (payload.get("resolvedProvider") or payload.get("requestedProvider") or payload.get("selectedProvider")) is not None else None,
            invocationKind="chat-completion",
            status=str(payload.get("status") or "running"),
            traceId=str(payload.get("traceId")) if payload.get("traceId") is not None else None,
            promptCompileArtifactId=str(payload.get("promptCompileArtifactId")) if payload.get("promptCompileArtifactId") is not None else None,
            requestRef=_external_ref(payload.get("requestRef")),
            responseRef=_external_ref(payload.get("responseRef")),
            inputTokensUsed=int(payload.get("inputTokensUsed", 0)),
            outputTokensUsed=int(payload.get("outputTokensUsed", 0)),
            costUsed=float(payload.get("costUsed", 0.0)),
            latencyMs=float(payload["latencyMs"]) if payload.get("latencyMs") is not None else None,
            errorSummary=str(payload.get("errorSummary")) if payload.get("errorSummary") is not None else None,
            startedAt=payload.get("startedAt") or utc_now(),
            endedAt=payload.get("endedAt"),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = ModelInvocationORM(
            id=record.id,
            app_id=record.app_id,
            project_id=record.project_id,
            task_id=record.task_id,
            agent_run_id=record.agent_run_id,
            route_decision_id=record.route_decision_id,
            requested_model=record.requested_model,
            requested_provider=record.requested_provider,
            resolved_model=record.resolved_model,
            resolved_provider=record.resolved_provider,
            invocation_kind=record.invocation_kind,
            status=record.status,
            trace_id=record.trace_id,
            prompt_compile_artifact_id=record.prompt_compile_artifact_id,
            request_ref=record.request_ref.model_dump(mode="json") if record.request_ref is not None else None,
            response_ref=record.response_ref.model_dump(mode="json") if record.response_ref is not None else None,
            input_tokens_used=record.input_tokens_used,
            output_tokens_used=record.output_tokens_used,
            cost_used=record.cost_used,
            latency_ms=record.latency_ms,
            error_summary=record.error_summary,
            started_at=record.started_at,
            ended_at=record.ended_at,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _model_invocation_record(model)

    def update_model_invocation(self, invocation_id: str, payload: dict[str, Any]) -> ModelInvocationRecord:
        model = self.session.get(ModelInvocationORM, invocation_id)
        if model is None:
            raise KeyError(invocation_id)
        if "status" in payload:
            model.status = str(payload["status"])
        if "traceId" in payload:
            model.trace_id = str(payload["traceId"]) if payload["traceId"] is not None else None
        if "promptCompileArtifactId" in payload:
            model.prompt_compile_artifact_id = str(payload["promptCompileArtifactId"]) if payload["promptCompileArtifactId"] is not None else None
        if "resolvedModel" in payload:
            model.resolved_model = str(payload["resolvedModel"])
        if "resolvedProvider" in payload:
            model.resolved_provider = str(payload["resolvedProvider"]) if payload["resolvedProvider"] is not None else None
        if "requestRef" in payload:
            model.request_ref = _external_ref(payload["requestRef"]).model_dump(mode="json") if payload["requestRef"] is not None else None
        if "responseRef" in payload:
            model.response_ref = _external_ref(payload["responseRef"]).model_dump(mode="json") if payload["responseRef"] is not None else None
        if "inputTokensUsed" in payload:
            model.input_tokens_used = int(payload["inputTokensUsed"])
        if "outputTokensUsed" in payload:
            model.output_tokens_used = int(payload["outputTokensUsed"])
        if "costUsed" in payload:
            model.cost_used = float(payload["costUsed"])
        if "latencyMs" in payload:
            model.latency_ms = float(payload["latencyMs"]) if payload["latencyMs"] is not None else None
        if "errorSummary" in payload:
            model.error_summary = str(payload["errorSummary"]) if payload["errorSummary"] is not None else None
        if "endedAt" in payload:
            model.ended_at = payload["endedAt"]
        self.session.flush()
        return _model_invocation_record(model)

    def list_model_invocations(
        self,
        *,
        task_id: str | None = None,
        agent_run_id: str | None = None,
        app_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[ModelInvocationRecord]:
        statement = sa.select(ModelInvocationORM).order_by(ModelInvocationORM.created_at.desc()).limit(limit)
        if task_id:
            statement = statement.where(ModelInvocationORM.task_id == task_id)
        if agent_run_id:
            statement = statement.where(ModelInvocationORM.agent_run_id == agent_run_id)
        if app_id:
            statement = statement.where(ModelInvocationORM.app_id == app_id)
        if status:
            statement = statement.where(ModelInvocationORM.status == status)
        return [_model_invocation_record(model) for model in self.session.execute(statement).scalars().all()]

class OutboxRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_event(self, payload: dict[str, Any]) -> OutboxRecord:
        record = OutboxRecord(
            id=str(payload.get("id") or new_id("outbox", payload.get("aggregateType"), payload.get("aggregateId"), utc_now().isoformat())),
            projectId=str(payload.get("projectId")) if payload.get("projectId") is not None else None,
            aggregateType=str(payload.get("aggregateType") or "unknown"),
            aggregateId=str(payload.get("aggregateId") or "unknown"),
            eventType=str(payload.get("eventType") or "unknown"),
            eventVersion=int(payload.get("eventVersion", 1)),
            payloadRef=_external_ref(payload.get("payloadRef") or {"type": "package-entry", "locator": "system/unknown"}),
            publishStatus=str(payload.get("publishStatus") or "pending"),
            attempts=int(payload.get("attempts", 0)),
            availableAt=payload.get("availableAt") or utc_now(),
            publishedAt=payload.get("publishedAt"),
            lastError=str(payload.get("lastError")) if payload.get("lastError") is not None else None,
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = OutboxRecordORM(
            id=record.id,
            project_id=record.project_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            event_type=record.event_type,
            event_version=record.event_version,
            payload_ref=record.payload_ref.model_dump(mode="json"),
            publish_status=record.publish_status,
            attempts=record.attempts,
            available_at=record.available_at,
            published_at=record.published_at,
            last_error=record.last_error,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return record

    def list_events(self, *, publish_status: str | None = None, limit: int = 100) -> list[OutboxRecord]:
        statement = sa.select(OutboxRecordORM).order_by(OutboxRecordORM.created_at.desc()).limit(limit)
        if publish_status:
            statement = statement.where(OutboxRecordORM.publish_status == publish_status)
        return [_outbox_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_event(self, event_id: str) -> OutboxRecord | None:
        model = self.session.get(OutboxRecordORM, event_id)
        return _outbox_record(model) if model is not None else None

    def claim_events(self, *, limit: int = 100, now: datetime | None = None) -> list[OutboxRecord]:
        current_time = now or utc_now()
        statement = (
            sa.select(OutboxRecordORM)
            .where(OutboxRecordORM.publish_status == "pending")
            .where(OutboxRecordORM.available_at <= current_time)
            .order_by(OutboxRecordORM.created_at.asc())
            .limit(limit)
        )
        models = self.session.execute(statement).scalars().all()
        for model in models:
            model.publish_status = "publishing"
            model.attempts += 1
        self.session.flush()
        return [_outbox_record(model) for model in models]

    def mark_published(self, event_id: str, *, published_at: datetime | None = None) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "published"
        model.published_at = published_at or utc_now()
        model.last_error = None
        self.session.flush()
        return _outbox_record(model)

    def mark_pending(
        self,
        event_id: str,
        *,
        last_error: str | None = None,
        available_at: datetime | None = None,
    ) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "pending"
        model.available_at = available_at or utc_now()
        model.last_error = last_error
        self.session.flush()
        return _outbox_record(model)

    def mark_dead_letter(self, event_id: str, *, last_error: str) -> OutboxRecord:
        model = self.session.get(OutboxRecordORM, event_id)
        if model is None:
            raise KeyError(event_id)
        model.publish_status = "dead-letter"
        model.last_error = last_error
        self.session.flush()
        return _outbox_record(model)


__all__ = [name for name in globals() if not name.startswith("__")]
