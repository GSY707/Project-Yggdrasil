from ._base import *  # noqa: F403,F401

class EvaluationServiceMixin:
    def list_evaluation_suites(self) -> dict[str, object]:
        definitions = {
            str(definition.get("id")): definition
            for definition in list_evaluation_suite_definitions(self.workspace_root)
        }
        ensure_evaluation_suites(self.workspace_root)
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            suites = EvaluationRepository(session).list_suites(limit=200)
        return {
            "evaluationSuites": [
                {
                    **suite.model_dump(by_alias=True, mode="json"),
                    "caseCount": len(definitions.get(suite.id, {}).get("cases") or []),
                    "cases": list(definitions.get(suite.id, {}).get("cases") or []),
                    "subjectKind": definitions.get(suite.id, {}).get("subjectKind", "workflow"),
                    "subjectRef": definitions.get(suite.id, {}).get("subjectRef", suite.id),
                }
                for suite in suites
            ]
        }

    def list_evaluation_runs(
        self,
        *,
        suite_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> dict[str, object]:
        ensure_evaluation_suites(self.workspace_root)
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            runs = EvaluationRepository(session).list_runs(suite_id=suite_id, status=status, limit=limit)
        return {
            "evaluationRuns": [
                {
                    **run.model_dump(by_alias=True, mode="json"),
                    "metrics": self._load_metrics_payload(run.metrics_ref.locator if run.metrics_ref else None),
                }
                for run in runs
            ]
        }

    def execute_evaluation_suite(self, suite_id: str) -> dict[str, object]:
        return run_evaluation_suite(suite_id, self.workspace_root)


