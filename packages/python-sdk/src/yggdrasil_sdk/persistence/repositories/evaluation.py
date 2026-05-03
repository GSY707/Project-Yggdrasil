from ._common import *

class EvaluationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_suites(self, *, domain: str | None = None, limit: int = 100) -> list[EvaluationSuiteRecord]:
        statement = sa.select(EvaluationSuiteORM).order_by(EvaluationSuiteORM.created_at.asc()).limit(limit)
        if domain is not None:
            statement = statement.where(EvaluationSuiteORM.domain == domain)
        return [_evaluation_suite_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_suite(self, suite_id: str) -> EvaluationSuiteRecord | None:
        model = self.session.get(EvaluationSuiteORM, suite_id)
        return _evaluation_suite_record(model) if model is not None else None

    def upsert_suite(self, record: EvaluationSuiteRecord) -> EvaluationSuiteRecord:
        model = self.session.get(EvaluationSuiteORM, record.id)
        if model is None:
            model = EvaluationSuiteORM(id=record.id)
            self.session.add(model)
        model.name = record.name
        model.domain = record.domain
        model.metric_refs = list(record.metric_refs)
        model.created_at = record.created_at
        self.session.flush()
        return _evaluation_suite_record(model)

    def list_runs(
        self,
        *,
        suite_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[EvaluationRunRecord]:
        statement = sa.select(EvaluationRunORM).order_by(EvaluationRunORM.created_at.desc()).limit(limit)
        if suite_id is not None:
            statement = statement.where(EvaluationRunORM.suite_id == suite_id)
        if status is not None:
            statement = statement.where(EvaluationRunORM.status == status)
        return [_evaluation_run_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_run(self, run_id: str) -> EvaluationRunRecord | None:
        model = self.session.get(EvaluationRunORM, run_id)
        return _evaluation_run_record(model) if model is not None else None

    def create_run(self, payload: dict[str, Any]) -> EvaluationRunRecord:
        suite_id = str(payload.get("suiteId") or "")
        if not suite_id:
            raise KeyError("suiteId")
        if self.session.get(EvaluationSuiteORM, suite_id) is None:
            raise KeyError(f"Evaluation suite {suite_id} not found.")
        record = EvaluationRunRecord(
            id=str(payload.get("id") or new_id("evalrun", suite_id, utc_now().isoformat())),
            suiteId=suite_id,
            projectId=str(payload.get("projectId") or DEFAULT_PROJECT_ID),
            subjectKind=str(payload.get("subjectKind") or "workflow"),
            subjectRef=str(payload.get("subjectRef") or suite_id),
            status=str(payload.get("status") or "queued"),
            metricsRef=_external_ref(payload.get("metricsRef")),
            startedAt=payload.get("startedAt"),
            endedAt=payload.get("endedAt"),
            createdAt=payload.get("createdAt") or utc_now(),
        )
        model = EvaluationRunORM(
            id=record.id,
            suite_id=record.suite_id,
            project_id=record.project_id,
            subject_kind=record.subject_kind,
            subject_ref=record.subject_ref,
            status=record.status,
            metrics_ref=record.metrics_ref.model_dump(mode="json") if record.metrics_ref else None,
            started_at=record.started_at,
            ended_at=record.ended_at,
            created_at=record.created_at,
        )
        self.session.add(model)
        self.session.flush()
        return _evaluation_run_record(model)

    def update_run(self, run_id: str, payload: dict[str, Any]) -> EvaluationRunRecord:
        model = self.session.get(EvaluationRunORM, run_id)
        if model is None:
            raise KeyError(f"Evaluation run {run_id} not found.")
        if "status" in payload:
            model.status = str(payload.get("status") or model.status)
        if "metricsRef" in payload:
            metrics_ref = _external_ref(payload.get("metricsRef"))
            model.metrics_ref = metrics_ref.model_dump(mode="json") if metrics_ref is not None else None
        if "startedAt" in payload:
            model.started_at = payload.get("startedAt")
        if "endedAt" in payload:
            model.ended_at = payload.get("endedAt")
        self.session.flush()
        return _evaluation_run_record(model)

