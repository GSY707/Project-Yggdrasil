from ._base import *  # noqa: F403,F401

class CollaborationServiceMixin:
    def list_pull_requests(
        self,
        *,
        project_id: str | None = None,
        source_branch_id: str | None = None,
        target_branch_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            pull_requests = CollaborationRepository(session).list_pull_requests(
                project_id=project_id,
                source_branch_id=source_branch_id,
                target_branch_id=target_branch_id,
                status=status,
                limit=limit,
            )
        return {"pullRequests": [record.model_dump(by_alias=True, mode="json") for record in pull_requests]}

    def get_pull_request(self, pr_id: str) -> dict[str, object]:
        with self.runtime.session_scope() as session:
            WorkspaceBootstrapRepository(session).ensure_default_workspace()
            collaboration_repository = CollaborationRepository(session)
            pull_request = collaboration_repository.get_pull_request(pr_id)
            if pull_request is None:
                raise KeyError(pr_id)
            review_comments = collaboration_repository.list_review_comments(pr_id)
        return {
            "pullRequest": pull_request.model_dump(by_alias=True, mode="json"),
            "reviewComments": [comment.model_dump(by_alias=True, mode="json") for comment in review_comments],
        }

    def launch_subagent(self, parent_task_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return launch_subagent_task(parent_task_id, payload)

    def create_pull_request(self, payload: dict[str, Any]) -> dict[str, object]:
        return create_collaboration_pull_request(payload)

    def review_pull_request(self, pr_id: str, payload: dict[str, Any]) -> dict[str, object]:
        return review_collaboration_pull_request(pr_id, payload)


