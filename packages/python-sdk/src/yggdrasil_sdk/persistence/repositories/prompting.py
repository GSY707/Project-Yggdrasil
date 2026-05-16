from ._common import *

class PromptAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_prompt_compile_artifacts(
        self,
        *,
        project_id: str | None = None,
        task_id: str | None = None,
        app_id: str | None = None,
        limit: int = 100,
    ) -> list[PromptCompileArtifactRecord]:
        statement = sa.select(PromptCompileArtifactORM).order_by(PromptCompileArtifactORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(PromptCompileArtifactORM.project_id == project_id)
        if task_id is not None:
            statement = statement.where(PromptCompileArtifactORM.task_id == task_id)
        if app_id is not None:
            statement = statement.where(PromptCompileArtifactORM.app_id == app_id)
        return [_prompt_compile_artifact_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_prompt_profile_version(self, record: PromptProfileVersionRecord) -> PromptProfileVersionRecord:
        statement = sa.select(PromptProfileVersionORM).where(PromptProfileVersionORM.id == record.id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = PromptProfileVersionORM(id=record.id)
            self.session.add(model)
        model.prompt_profile_id = record.prompt_profile_id
        model.name = record.name
        model.version = record.version
        model.run_scope = record.run_scope
        model.body = dict(record.body)
        model.content_hash = record.content_hash
        model.created_at = record.created_at
        self.session.flush()
        return _prompt_profile_version_record(model)

    def upsert_seed_template_version(self, record: SeedTemplateVersionRecord) -> SeedTemplateVersionRecord:
        statement = sa.select(SeedTemplateVersionORM).where(SeedTemplateVersionORM.id == record.id)
        model = self.session.execute(statement).scalar_one_or_none()
        if model is None:
            model = SeedTemplateVersionORM(id=record.id)
            self.session.add(model)
        model.seed_template_id = record.seed_template_id
        model.name = record.name
        model.version = record.version
        model.domain = record.domain
        model.scenario = record.scenario
        model.body = dict(record.body)
        model.content_hash = record.content_hash
        model.created_at = record.created_at
        self.session.flush()
        return _seed_template_version_record(model)

    def create_prompt_compile_artifact(self, payload: dict[str, Any]) -> PromptCompileArtifactRecord:
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        task_id = str(payload.get("taskId")) if payload.get("taskId") is not None else None
        agent_run_id = str(payload.get("agentRunId")) if payload.get("agentRunId") is not None else None
        model_invocation_id = str(payload.get("modelInvocationId")) if payload.get("modelInvocationId") is not None else None
        task = self.session.get(TaskORM, task_id) if task_id is not None else None
        run = self.session.get(AgentRunORM, agent_run_id) if agent_run_id is not None else None
        invocation = self.session.get(ModelInvocationORM, model_invocation_id) if model_invocation_id is not None else None
        if self.session.get(ProjectORM, project_id) is None:
            raise KeyError(f"Project {project_id} not found.")
        if task_id is not None and task is None:
            raise KeyError(f"Task {task_id} not found.")
        if agent_run_id is not None and run is None:
            raise KeyError(f"Agent run {agent_run_id} not found.")
        if model_invocation_id is not None and invocation is None:
            raise KeyError(f"Model invocation {model_invocation_id} not found.")
        if task is not None and run is not None and task.app_id != run.app_id:
            raise ValueError(f"Task {task_id} appId {task.app_id} does not match agent run {agent_run_id} appId {run.app_id}.")
        if task is not None and invocation is not None and task.app_id != invocation.app_id:
            raise ValueError(
                f"Task {task_id} appId {task.app_id} does not match model invocation {model_invocation_id} appId {invocation.app_id}."
            )
        if run is not None and invocation is not None and run.app_id != invocation.app_id:
            raise ValueError(
                f"Agent run {agent_run_id} appId {run.app_id} does not match model invocation {model_invocation_id} appId {invocation.app_id}."
            )
        app_id = str(
            payload.get("appId")
            or (task.app_id if task is not None else None)
            or (run.app_id if run is not None else None)
            or (invocation.app_id if invocation is not None else None)
            or DEFAULT_APP_ID
        )
        if task is not None and app_id != task.app_id:
            raise ValueError(f"Prompt compile artifact appId {app_id} does not match task {task_id} appId {task.app_id}.")
        if run is not None and app_id != run.app_id:
            raise ValueError(f"Prompt compile artifact appId {app_id} does not match agent run {agent_run_id} appId {run.app_id}.")
        if invocation is not None and app_id != invocation.app_id:
            raise ValueError(
                f"Prompt compile artifact appId {app_id} does not match model invocation {model_invocation_id} appId {invocation.app_id}."
            )
        record = PromptCompileArtifactRecord(
            id=str(payload.get("id") or new_id("promptcmp", payload.get("modelInvocationId") or payload.get("agentRunId") or utc_now().isoformat())),
            appId=app_id,
            projectId=project_id,
            taskId=task_id,
            agentRunId=agent_run_id,
            modelInvocationId=model_invocation_id,
            promptProfileVersionId=str(payload.get("promptProfileVersionId")),
            seedTemplateVersionId=str(payload.get("seedTemplateVersionId")) if payload.get("seedTemplateVersionId") is not None else None,
            runType=str(payload.get("runType") or "main"),
            taskType=str(payload.get("taskType") or "generic"),
            scenario=str(payload.get("scenario")) if payload.get("scenario") is not None else None,
            registeredTools=list(payload.get("registeredTools") or []),
            systemSections=dict(payload.get("systemSections") or {}),
            userSections=dict(payload.get("userSections") or {}),
            workTreeSnapshot=dict(payload.get("workTreeSnapshot") or {}) if payload.get("workTreeSnapshot") is not None else None,
            takeoverProtocolSnapshot=(
                dict(payload.get("takeoverProtocolSnapshot") or {}) if payload.get("takeoverProtocolSnapshot") is not None else None
            ),
            compiledMessagesRef=_external_ref(payload.get("compiledMessagesRef")),
            contentHash=str(payload.get("contentHash")),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        if self.session.get(PromptProfileVersionORM, record.prompt_profile_version_id) is None:
            raise KeyError(f"Prompt profile version {record.prompt_profile_version_id} not found.")
        if record.seed_template_version_id is not None and self.session.get(SeedTemplateVersionORM, record.seed_template_version_id) is None:
            raise KeyError(f"Seed template version {record.seed_template_version_id} not found.")
        model = PromptCompileArtifactORM(
            id=record.id,
            app_id=record.app_id,
            project_id=record.project_id,
            task_id=record.task_id,
            agent_run_id=record.agent_run_id,
            model_invocation_id=record.model_invocation_id,
            prompt_profile_version_id=record.prompt_profile_version_id,
            seed_template_version_id=record.seed_template_version_id,
            run_type=record.run_type,
            task_type=record.task_type,
            scenario=record.scenario,
            registered_tools=list(record.registered_tools),
            system_sections=dict(record.system_sections),
            user_sections=dict(record.user_sections),
            work_tree_snapshot=dict(record.work_tree_snapshot or {}) if record.work_tree_snapshot is not None else None,
            takeover_protocol_snapshot=(
                dict(record.takeover_protocol_snapshot or {}) if record.takeover_protocol_snapshot is not None else None
            ),
            compiled_messages_ref=record.compiled_messages_ref.model_dump(mode="json"),
            content_hash=record.content_hash,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _prompt_compile_artifact_record(model)

    def get_prompt_compile_artifact(self, artifact_id: str) -> PromptCompileArtifactRecord | None:
        model = self.session.get(PromptCompileArtifactORM, artifact_id)
        return _prompt_compile_artifact_record(model) if model is not None else None

    def update_run(self, run_id: str, payload: dict[str, Any]) -> EvaluationRunRecord:
        model = self.session.get(EvaluationRunORM, run_id)
        if model is None:
            raise KeyError(run_id)
        if "status" in payload:
            model.status = str(payload["status"])
        if "metricsRef" in payload:
            metrics_ref = _external_ref(payload["metricsRef"])
            model.metrics_ref = metrics_ref.model_dump(mode="json") if metrics_ref is not None else None
        if "startedAt" in payload:
            model.started_at = payload["startedAt"]
        if "endedAt" in payload:
            model.ended_at = payload["endedAt"]
        if "subjectRef" in payload:
            model.subject_ref = str(payload["subjectRef"])
        self.session.flush()
        return _evaluation_run_record(model)
