from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


JSON_TYPE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


class Base(DeclarativeBase):
    metadata = sa.MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class ProjectORM(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    export_policy: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class SpaceORM(Base):
    __tablename__ = "spaces"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    owner_subject: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class MemoryBranchORM(Base):
    __tablename__ = "memory_branches"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    base_branch_id: Mapped[str | None] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="SET NULL"), nullable=True)
    head_ref: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class SpaceMountORM(Base):
    __tablename__ = "space_mounts"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    host_space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    mounted_space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    mount_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class PermissionTupleORM(Base):
    __tablename__ = "permission_tuples"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    relation: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    resource: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    condition: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    effect: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class NodeORM(Base):
    __tablename__ = "nodes"
    __table_args__ = (
        sa.Index("ix_nodes_branch_created_at", "branch_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_id: Mapped[str | None] = mapped_column(sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    root_branch: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    node_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    content: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    detail_level: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    importance: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    stability: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    forget_rate: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    feedforward_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    access_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    activity_k: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    float_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    latest_version_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    merged_into_node_id: Mapped[str | None] = mapped_column(sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True)
    children_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    edge_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    tree_path: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    window_index: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=1)
    source_work_tree_node_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class EdgeORM(Base):
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    from_node_id: Mapped[str] = mapped_column(sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    to_node_id: Mapped[str] = mapped_column(sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relation_type: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    weight: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    evidence_annotation_ids: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class NodeVersionORM(Base):
    __tablename__ = "node_versions"
    __table_args__ = (sa.UniqueConstraint("node_id", "version_no"),)

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    node_id: Mapped[str] = mapped_column(sa.ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    title_snapshot: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    content_snapshot: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    parent_id_snapshot: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    score_snapshot: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    change_reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    derived_from_version_id: Mapped[str | None] = mapped_column(sa.ForeignKey("node_versions.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class SourceAnnotationORM(Base):
    __tablename__ = "source_annotations"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    owner_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    source_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    excerpt: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    inference_summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    evidence_refs: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class RetrievalRequestORM(Base):
    __tablename__ = "retrieval_requests"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    query_text: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    seed_node_refs: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    traversal_start: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    expansion_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    read_depth: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    lateral_hops: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    max_related_nodes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    max_leaf_nodes: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    precision_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    include_natural_language_summary: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    include_child_names: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    include_related_names: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    reverse_trace_mode: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    work_tree_node_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    window_index: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    token_budget: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ImportJobORM(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    source_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    import_policy: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    requested_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    token_budget: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    cost_budget: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    started_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    finished_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ImportFragmentORM(Base):
    __tablename__ = "import_fragments"
    __table_args__ = (
        sa.UniqueConstraint("import_job_id", "ordinal"),
        sa.Index("ix_import_fragments_job_created", "import_job_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    import_job_id: Mapped[str] = mapped_column(sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    raw_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    normalized_text: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    approx_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    related_hints: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class TreePlanORM(Base):
    __tablename__ = "tree_plans"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    import_job_id: Mapped[str] = mapped_column(sa.ForeignKey("import_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    candidate_node_payloads: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    candidate_edge_payloads: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    candidate_source_annotations: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    discarded_fragment_refs: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    rationale: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    proposed_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class TaskORM(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    app_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    goal: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    current_focus: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    current_objective: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    resume_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    restart_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    owner_profile_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    execution_root_node_id: Mapped[str | None] = mapped_column(sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True)
    active_snapshot_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    window_index: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=1)
    restart_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cumulative_window_span_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    carry_forward_loss_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    budget: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    pause_requested: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=False)
    last_safe_stop_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    started_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    ended_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class AgentRunORM(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    app_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True)
    run_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    selected_model: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    selected_provider: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    route_decision_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    next_objective: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    window_index: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=1)
    restart_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cumulative_window_span_tokens: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    input_tokens_used: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    output_tokens_used: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cost_used: Mapped[float] = mapped_column(sa.Float(), nullable=False, default=0.0)
    started_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ended_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class TaskSnapshotORM(Base):
    __tablename__ = "task_snapshots"
    __table_args__ = (
        sa.Index("ix_task_snapshots_task_status_created", "task_id", "status", "created_at"),
        sa.Index("ix_task_snapshots_task_created", "task_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    app_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id: Mapped[str] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    resume_token: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True)
    context_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    root_mount_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    pending_writes: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    pending_actions: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    resume_message: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    safe_stop_reason: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    safe_to_pause: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    current_node_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    working_node_annotation: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    pc_memo: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    top_frame_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    stack_digest: Mapped[str | None] = mapped_column(sa.String(64), nullable=True)
    blockers: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)


class ModelRouteDecisionORM(Base):
    __tablename__ = "model_route_decisions"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    task_id: Mapped[str | None] = mapped_column(sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    selected_model: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    selected_provider: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    candidate_models: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    reason: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    budget_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    quality_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    latency_score: Mapped[float] = mapped_column(sa.Float(), nullable=False)
    route_policy_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ModelInvocationORM(Base):
    __tablename__ = "model_invocations"
    __table_args__ = (
        sa.Index("ix_model_invocations_task_created", "task_id", "created_at"),
        sa.Index("ix_model_invocations_run_created", "agent_run_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    app_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    route_decision_id: Mapped[str | None] = mapped_column(sa.ForeignKey("model_route_decisions.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_model: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    requested_provider: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    resolved_model: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    resolved_provider: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    invocation_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    trace_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    prompt_compile_artifact_id: Mapped[str | None] = mapped_column(sa.ForeignKey("prompt_compile_artifacts.id", ondelete="SET NULL"), nullable=True, index=True)
    request_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    response_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    output_labels: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    assistant_text_summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    input_tokens_used: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    output_tokens_used: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    cost_used: Mapped[float] = mapped_column(sa.Float(), nullable=False, default=0.0)
    latency_ms: Mapped[float | None] = mapped_column(sa.Float(), nullable=True)
    error_summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    started_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    ended_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ModuleInstallORM(Base):
    __tablename__ = "module_installs"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    module_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, unique=True)
    module_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    desired_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    lifecycle_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    runtime_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    manifest_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    config_binding_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    installed_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    enabled_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    disabled_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)


class ModuleConfigBindingORM(Base):
    __tablename__ = "module_config_bindings"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    module_install_id: Mapped[str] = mapped_column(sa.ForeignKey("module_installs.id", ondelete="CASCADE"), nullable=False, unique=True)
    config_schema_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    effective_config_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    source_mode: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class HookContributionORM(Base):
    __tablename__ = "hook_contributions"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    module_install_id: Mapped[str] = mapped_column(sa.ForeignKey("module_installs.id", ondelete="CASCADE"), nullable=False, index=True)
    hook_name: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    implementation_ref: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    execution_order: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    side_effects: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class EventSubscriptionORM(Base):
    __tablename__ = "event_subscriptions"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    module_install_id: Mapped[str] = mapped_column(sa.ForeignKey("module_installs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    consumer_group: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    delivery_mode: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class HealthReportORM(Base):
    __tablename__ = "health_reports"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    module_install_id: Mapped[str] = mapped_column(sa.ForeignKey("module_installs.id", ondelete="CASCADE"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    details_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    observed_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class OutboxRecordORM(Base):
    __tablename__ = "outbox_records"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str | None] = mapped_column(sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    aggregate_type: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    event_version: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    payload_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    publish_status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(sa.Integer(), nullable=False, default=0)
    available_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    published_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class MailboxMessageORM(Base):
    __tablename__ = "mailbox_messages"
    __table_args__ = (
        sa.Index("ix_mailbox_messages_task_status_created", "task_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    sender: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    message_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    work_tree_node_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    wake_on_message: Mapped[bool] = mapped_column(sa.Boolean(), nullable=False, default=True)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, default="pending", index=True)
    payload_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    delivered_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class SideChannelEventORM(Base):
    __tablename__ = "side_channel_events"
    __table_args__ = (
        sa.Index("ix_side_channel_events_task_created", "task_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    source: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    event_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    level: Mapped[str] = mapped_column(sa.String(16), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    work_tree_node_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    payload_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class PullRequestORM(Base):
    __tablename__ = "pull_requests"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    target_branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="RESTRICT"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    reviewed_by: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    external_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    external_url: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    merge_commit_ref: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    merged_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ReviewCommentORM(Base):
    __tablename__ = "review_comments"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    pr_id: Mapped[str] = mapped_column(sa.ForeignKey("pull_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    author: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    target_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    body: Mapped[str] = mapped_column(sa.Text(), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    resolved_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)


class EvaluationSuiteORM(Base):
    __tablename__ = "evaluation_suites"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    domain: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    metric_refs: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class EvaluationRunORM(Base):
    __tablename__ = "evaluation_runs"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    suite_id: Mapped[str] = mapped_column(sa.ForeignKey("evaluation_suites.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    subject_kind: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    subject_ref: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    metrics_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    started_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    ended_at: Mapped[sa.DateTime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class AssetORM(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    space_id: Mapped[str] = mapped_column(sa.ForeignKey("spaces.id", ondelete="CASCADE"), nullable=False, index=True)
    branch_id: Mapped[str] = mapped_column(sa.ForeignKey("memory_branches.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_node_id: Mapped[str | None] = mapped_column(sa.ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True, index=True)
    media_type: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    role: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    checksum: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    source_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    related_work_tree_node_ids: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    width: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    height: Mapped[int | None] = mapped_column(sa.Integer(), nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    created_by: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)


class AssetSegmentORM(Base):
    __tablename__ = "asset_segments"
    __table_args__ = (sa.UniqueConstraint("asset_id", "ordinal"),)

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    asset_id: Mapped[str] = mapped_column(sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    ordinal: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    start_offset: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    end_offset: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    text_excerpt: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    summary: Mapped[str | None] = mapped_column(sa.Text(), nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(sa.String(128), nullable=True, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class AssetEmbeddingORM(Base):
    __tablename__ = "asset_embeddings"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    owner_kind: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    model: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    dimension: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    vector_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class DatasetVersionORM(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (sa.UniqueConstraint("dataset_name", "version"),)

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    dataset_name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    source_filter: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    row_count: Mapped[int] = mapped_column(sa.Integer(), nullable=False)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class ModelArtifactORM(Base):
    __tablename__ = "model_artifacts"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    base_model: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    tuning_method: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    dataset_version_id: Mapped[str] = mapped_column(sa.ForeignKey("dataset_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    metrics_ref: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    storage_key: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class PromptProfileVersionORM(Base):
    __tablename__ = "prompt_profile_versions"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    prompt_profile_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    run_scope: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    body: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class SeedTemplateVersionORM(Base):
    __tablename__ = "seed_template_versions"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    seed_template_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    version: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    domain: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    scenario: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    body: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)


class PromptCompileArtifactORM(Base):
    __tablename__ = "prompt_compile_artifacts"

    id: Mapped[str] = mapped_column(sa.String(128), primary_key=True)
    app_id: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(sa.ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(sa.ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True, index=True)
    model_invocation_id: Mapped[str | None] = mapped_column(sa.ForeignKey("model_invocations.id", ondelete="SET NULL"), nullable=True, index=True)
    prompt_profile_version_id: Mapped[str] = mapped_column(sa.ForeignKey("prompt_profile_versions.id", ondelete="RESTRICT"), nullable=False, index=True)
    seed_template_version_id: Mapped[str | None] = mapped_column(sa.ForeignKey("seed_template_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    run_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    task_type: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    scenario: Mapped[str | None] = mapped_column(sa.String(255), nullable=True)
    registered_tools: Mapped[list] = mapped_column(JSON_TYPE, nullable=False, default=list)
    boot_sections: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False, default=dict)
    system_sections: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    user_sections: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    work_tree_snapshot: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    takeover_protocol_snapshot: Mapped[dict | None] = mapped_column(JSON_TYPE, nullable=True)
    compiled_messages_ref: Mapped[dict] = mapped_column(JSON_TYPE, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    created_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime(timezone=True), nullable=False)