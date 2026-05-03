from ._common import *

class CollaborationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_spaces(
        self,
        *,
        project_id: str | None = None,
        space_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SpaceRecord]:
        statement = sa.select(SpaceORM).order_by(SpaceORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(SpaceORM.project_id == project_id)
        if space_type is not None:
            statement = statement.where(SpaceORM.space_type == space_type)
        if status is not None:
            statement = statement.where(SpaceORM.status == status)
        return [_space_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_space(self, space_id: str) -> SpaceRecord | None:
        model = self.session.get(SpaceORM, space_id)
        return _space_record(model) if model else None

    def create_space(self, payload: dict[str, Any]) -> SpaceRecord:
        now = payload.get("createdAt") or utc_now()
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        if self.session.get(ProjectORM, project_id) is None:
            raise KeyError(project_id)

        space_id = str(payload.get("id") or new_id("space", payload.get("spaceType") or payload.get("ownerSubject") or now.isoformat()))
        if self.session.get(SpaceORM, space_id) is not None:
            raise ValueError(f"Space {space_id} already exists.")

        model = SpaceORM(
            id=space_id,
            project_id=project_id,
            space_type=str(payload.get("spaceType") or "shared"),
            status=str(payload.get("status") or "active"),
            owner_subject=str(payload["ownerSubject"]) if payload.get("ownerSubject") is not None else None,
            created_at=now,
        )
        self.session.add(model)
        self.session.flush()
        return _space_record(model)

    def list_branches(
        self,
        *,
        project_id: str | None = None,
        space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[MemoryBranchRecord]:
        statement = sa.select(MemoryBranchORM).order_by(MemoryBranchORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(MemoryBranchORM.project_id == project_id)
        if space_id is not None:
            statement = statement.where(MemoryBranchORM.space_id == space_id)
        if status is not None:
            statement = statement.where(MemoryBranchORM.status == status)
        return [_branch_record(model) for model in self.session.execute(statement).scalars().all()]

    def list_space_mounts(
        self,
        *,
        project_id: str | None = None,
        host_space_id: str | None = None,
        mounted_space_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[SpaceMountRecord]:
        statement = sa.select(SpaceMountORM).order_by(SpaceMountORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(SpaceMountORM.project_id == project_id)
        if host_space_id is not None:
            statement = statement.where(SpaceMountORM.host_space_id == host_space_id)
        if mounted_space_id is not None:
            statement = statement.where(SpaceMountORM.mounted_space_id == mounted_space_id)
        if status is not None:
            statement = statement.where(SpaceMountORM.status == status)
        return [_space_mount_record(model) for model in self.session.execute(statement).scalars().all()]

    def create_space_mount(self, payload: dict[str, Any]) -> SpaceMountRecord:
        now = payload.get("createdAt") or utc_now()
        actor = _actor(payload.get("createdBy"), default_type="user", default_id="core-api")
        host_space_id = str(payload["hostSpaceId"])
        mounted_space_id = str(payload["mountedSpaceId"])
        mount_mode = str(payload.get("mountMode") or "readonly")

        if host_space_id == mounted_space_id:
            raise ValueError("Space mount cannot target the same space as both host and mounted source.")

        host_space = self.session.get(SpaceORM, host_space_id)
        mounted_space = self.session.get(SpaceORM, mounted_space_id)
        if host_space is None:
            raise KeyError(host_space_id)
        if mounted_space is None:
            raise KeyError(mounted_space_id)

        project_id = str(payload.get("projectId") or host_space.project_id)
        if self.session.get(ProjectORM, project_id) is None:
            raise KeyError(project_id)
        if host_space.project_id != project_id or mounted_space.project_id != project_id:
            raise ValueError("Host space and mounted space must belong to the same project.")

        duplicate_statement = (
            sa.select(SpaceMountORM)
            .where(SpaceMountORM.project_id == project_id)
            .where(SpaceMountORM.host_space_id == host_space_id)
            .where(SpaceMountORM.mounted_space_id == mounted_space_id)
            .where(SpaceMountORM.mount_mode == mount_mode)
            .where(SpaceMountORM.status != "detached")
            .limit(1)
        )
        duplicate = self.session.execute(duplicate_statement).scalar_one_or_none()
        if duplicate is not None:
            raise ValueError(
                f"Space mount already exists for {host_space_id} -> {mounted_space_id} in mode {mount_mode}."
            )

        model = SpaceMountORM(
            id=str(payload.get("id") or new_id("mount", host_space_id, mounted_space_id, mount_mode, now.isoformat())),
            project_id=project_id,
            host_space_id=host_space_id,
            mounted_space_id=mounted_space_id,
            mount_mode=mount_mode,
            status=str(payload.get("status") or "active"),
            created_at=now,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.flush()
        return _space_mount_record(model)

    def list_permission_tuples(
        self,
        *,
        project_id: str | None = None,
        subject: str | None = None,
        relation: str | None = None,
        resource: str | None = None,
        effect: str | None = None,
        limit: int = 100,
    ) -> list[PermissionTupleRecord]:
        statement = sa.select(PermissionTupleORM).order_by(PermissionTupleORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(PermissionTupleORM.project_id == project_id)
        if subject is not None:
            statement = statement.where(PermissionTupleORM.subject == subject)
        if relation is not None:
            statement = statement.where(PermissionTupleORM.relation == relation)
        if resource is not None:
            statement = statement.where(PermissionTupleORM.resource == resource)
        if effect is not None:
            statement = statement.where(PermissionTupleORM.effect == effect)
        return [_permission_tuple_record(model) for model in self.session.execute(statement).scalars().all()]

    def create_permission_tuple(self, payload: dict[str, Any]) -> PermissionTupleRecord:
        now = payload.get("createdAt") or utc_now()
        actor = _actor(payload.get("createdBy"), default_type="user", default_id="core-api")
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        if self.session.get(ProjectORM, project_id) is None:
            raise KeyError(project_id)

        subject = str(payload["subject"])
        relation = str(payload["relation"])
        resource = str(payload["resource"])
        condition = payload.get("condition")
        if condition is not None and not isinstance(condition, dict):
            raise ValueError("Permission tuple condition must be an object when provided.")
        effect = str(payload.get("effect") or "allow")

        duplicate_statement = (
            sa.select(PermissionTupleORM)
            .where(PermissionTupleORM.project_id == project_id)
            .where(PermissionTupleORM.subject == subject)
            .where(PermissionTupleORM.relation == relation)
            .where(PermissionTupleORM.resource == resource)
            .where(PermissionTupleORM.effect == effect)
        )
        for existing in self.session.execute(duplicate_statement).scalars().all():
            existing_condition = dict(existing.condition or {}) if existing.condition is not None else None
            if existing_condition == condition:
                raise ValueError(
                    f"Permission tuple already exists for {subject} {relation} {resource} ({effect})."
                )

        model = PermissionTupleORM(
            id=str(payload.get("id") or new_id("perm", project_id, subject, relation, resource, effect, now.isoformat())),
            project_id=project_id,
            subject=subject,
            relation=relation,
            resource=resource,
            condition=dict(condition) if condition is not None else None,
            effect=effect,
            created_at=now,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(model)
        self.session.flush()
        return _permission_tuple_record(model)

    def get_branch(self, branch_id: str) -> MemoryBranchRecord | None:
        model = self.session.get(MemoryBranchORM, branch_id)
        return _branch_record(model) if model else None

    def create_branch(self, payload: dict[str, Any]) -> MemoryBranchRecord:
        now = utc_now()
        actor = _actor(payload.get("createdBy"), default_type="agent", default_id="subagent")
        branch_id = str(payload.get("id") or new_id("branch", payload.get("name") or now.isoformat()))
        project_id = str(payload.get("projectId") or DEFAULT_PROJECT_ID)
        space_id = str(payload.get("spaceId") or DEFAULT_SPACE_ID)
        if self.session.get(MemoryBranchORM, branch_id) is not None:
            raise ValueError(f"Branch {branch_id} already exists.")
        branch = MemoryBranchORM(
            id=branch_id,
            project_id=project_id,
            space_id=space_id,
            name=str(payload.get("name") or branch_id),
            base_branch_id=str(payload["baseBranchId"]) if payload.get("baseBranchId") is not None else None,
            head_ref=str(payload["headRef"]) if payload.get("headRef") is not None else None,
            status=str(payload.get("status") or "active"),
            created_at=now,
            created_by=actor.model_dump(mode="json"),
        )
        self.session.add(branch)
        self.session.flush()
        _ensure_branch_roots(
            self.session,
            project_id=project_id,
            space_id=space_id,
            branch_id=branch_id,
            created_by=actor,
            now=now,
        )
        return _branch_record(branch)

    def update_branch(self, branch_id: str, payload: dict[str, Any]) -> MemoryBranchRecord:
        branch = self.session.get(MemoryBranchORM, branch_id)
        if branch is None:
            raise KeyError(branch_id)
        if "name" in payload:
            branch.name = str(payload["name"])
        if "baseBranchId" in payload:
            branch.base_branch_id = str(payload["baseBranchId"]) if payload["baseBranchId"] is not None else None
        if "headRef" in payload:
            branch.head_ref = str(payload["headRef"]) if payload["headRef"] is not None else None
        if "status" in payload:
            branch.status = str(payload["status"])
        self.session.flush()
        return _branch_record(branch)

    def list_pull_requests(
        self,
        *,
        project_id: str | None = None,
        source_branch_id: str | None = None,
        target_branch_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[PullRequestRecord]:
        statement = sa.select(PullRequestORM).order_by(PullRequestORM.created_at.desc()).limit(limit)
        if project_id is not None:
            statement = statement.where(PullRequestORM.project_id == project_id)
        if source_branch_id is not None:
            statement = statement.where(PullRequestORM.source_branch_id == source_branch_id)
        if target_branch_id is not None:
            statement = statement.where(PullRequestORM.target_branch_id == target_branch_id)
        if status is not None:
            statement = statement.where(PullRequestORM.status == status)
        return [_pull_request_record(model) for model in self.session.execute(statement).scalars().all()]

    def get_pull_request(self, pr_id: str) -> PullRequestRecord | None:
        model = self.session.get(PullRequestORM, pr_id)
        return _pull_request_record(model) if model else None

    def update_pull_request(self, pr_id: str, payload: dict[str, Any]) -> PullRequestRecord:
        model = self.session.get(PullRequestORM, pr_id)
        if model is None:
            raise KeyError(pr_id)
        if "title" in payload:
            model.title = str(payload["title"])
        if "summary" in payload:
            model.summary = str(payload["summary"])
        if "status" in payload:
            model.status = str(payload["status"])
        if "reviewedBy" in payload:
            reviewed_by = payload["reviewedBy"]
            model.reviewed_by = _actor(reviewed_by).model_dump(mode="json") if reviewed_by is not None else None
        if "externalId" in payload:
            model.external_id = str(payload["externalId"]) if payload["externalId"] is not None else None
        if "externalUrl" in payload:
            model.external_url = str(payload["externalUrl"]) if payload["externalUrl"] is not None else None
        if "mergeCommitRef" in payload:
            model.merge_commit_ref = str(payload["mergeCommitRef"]) if payload["mergeCommitRef"] is not None else None
        if "mergedAt" in payload:
            model.merged_at = payload["mergedAt"]
        self.session.flush()
        return _pull_request_record(model)

    def list_review_comments(self, pr_id: str, *, limit: int = 200) -> list[ReviewCommentRecord]:
        statement = (
            sa.select(ReviewCommentORM)
            .where(ReviewCommentORM.pr_id == pr_id)
            .order_by(ReviewCommentORM.created_at.asc())
            .limit(limit)
        )
        return [_review_comment_record(model) for model in self.session.execute(statement).scalars().all()]

    def upsert_pull_request(self, record: PullRequestRecord) -> PullRequestRecord:
        model = self.session.get(PullRequestORM, record.id)
        if model is None:
            model = PullRequestORM(id=record.id)
            self.session.add(model)
        model.project_id = record.project_id
        model.source_branch_id = record.source_branch_id
        model.target_branch_id = record.target_branch_id
        model.title = record.title
        model.summary = record.summary
        model.status = record.status
        model.created_by = record.created_by.model_dump(mode="json")
        model.reviewed_by = record.reviewed_by.model_dump(mode="json") if record.reviewed_by else None
        model.external_id = record.external_id
        model.external_url = record.external_url
        model.merge_commit_ref = record.merge_commit_ref
        model.merged_at = record.merged_at
        model.created_at = record.created_at
        self.session.flush()
        return _pull_request_record(model)

    def add_review_comment(self, record: ReviewCommentRecord) -> ReviewCommentRecord:
        model = ReviewCommentORM(
            id=record.id,
            pr_id=record.pr_id,
            author=record.author.model_dump(mode="json"),
            target_kind=record.target_kind,
            target_id=record.target_id,
            body=record.body,
            status=record.status,
            created_at=record.created_at,
            resolved_at=record.resolved_at,
        )
        self.session.add(model)
        self.session.flush()
        return _review_comment_record(model)

