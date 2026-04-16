"""memory_pipeline_tables

Revision ID: e7a4c55d7d4b
Revises: 553bffc21802
Create Date: 2026-04-16 23:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


Text = sa.Text


revision = "e7a4c55d7d4b"
down_revision = "553bffc21802"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("branch_id", sa.String(length=128), nullable=False),
        sa.Column("source_kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("import_policy", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("requested_by", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("token_budget", sa.Integer(), nullable=True),
        sa.Column("cost_budget", sa.Float(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["memory_branches.id"], name=op.f("fk_import_jobs_branch_id_memory_branches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_import_jobs_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_jobs")),
    )
    op.create_index(op.f("ix_import_jobs_branch_id"), "import_jobs", ["branch_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_project_id"), "import_jobs", ["project_id"], unique=False)
    op.create_index(op.f("ix_import_jobs_status"), "import_jobs", ["status"], unique=False)

    op.create_table(
        "retrieval_requests",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("branch_id", sa.String(length=128), nullable=False),
        sa.Column("query_text", sa.Text(), nullable=True),
        sa.Column("seed_node_refs", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("traversal_start", sa.String(length=32), nullable=False),
        sa.Column("expansion_mode", sa.String(length=32), nullable=False),
        sa.Column("read_depth", sa.Integer(), nullable=False),
        sa.Column("lateral_hops", sa.Integer(), nullable=False),
        sa.Column("max_related_nodes", sa.Integer(), nullable=False),
        sa.Column("max_leaf_nodes", sa.Integer(), nullable=False),
        sa.Column("precision_mode", sa.String(length=32), nullable=False),
        sa.Column("include_natural_language_summary", sa.Boolean(), nullable=False),
        sa.Column("include_child_names", sa.Boolean(), nullable=False),
        sa.Column("include_related_names", sa.Boolean(), nullable=False),
        sa.Column("token_budget", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["memory_branches.id"], name=op.f("fk_retrieval_requests_branch_id_memory_branches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_retrieval_requests_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], name=op.f("fk_retrieval_requests_space_id_spaces"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retrieval_requests")),
    )
    op.create_index(op.f("ix_retrieval_requests_branch_id"), "retrieval_requests", ["branch_id"], unique=False)
    op.create_index(op.f("ix_retrieval_requests_project_id"), "retrieval_requests", ["project_id"], unique=False)
    op.create_index(op.f("ix_retrieval_requests_space_id"), "retrieval_requests", ["space_id"], unique=False)

    op.create_table(
        "import_fragments",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("import_job_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("raw_ref", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("approx_tokens", sa.Integer(), nullable=False),
        sa.Column("related_hints", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], name=op.f("fk_import_fragments_import_job_id_import_jobs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_import_fragments")),
        sa.UniqueConstraint("import_job_id", "ordinal", name=op.f("uq_import_fragments_import_job_id")),
    )
    op.create_index(op.f("ix_import_fragments_import_job_id"), "import_fragments", ["import_job_id"], unique=False)

    op.create_table(
        "tree_plans",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("import_job_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("candidate_node_payloads", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("candidate_edge_payloads", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("candidate_source_annotations", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("discarded_fragment_refs", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("proposed_by", sa.JSON().with_variant(postgresql.JSONB(astext_type=Text()), "postgresql"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["import_job_id"], ["import_jobs.id"], name=op.f("fk_tree_plans_import_job_id_import_jobs"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tree_plans")),
    )
    op.create_index(op.f("ix_tree_plans_import_job_id"), "tree_plans", ["import_job_id"], unique=False)
    op.create_index(op.f("ix_tree_plans_status"), "tree_plans", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tree_plans_status"), table_name="tree_plans")
    op.drop_index(op.f("ix_tree_plans_import_job_id"), table_name="tree_plans")
    op.drop_table("tree_plans")

    op.drop_index(op.f("ix_import_fragments_import_job_id"), table_name="import_fragments")
    op.drop_table("import_fragments")

    op.drop_index(op.f("ix_retrieval_requests_space_id"), table_name="retrieval_requests")
    op.drop_index(op.f("ix_retrieval_requests_project_id"), table_name="retrieval_requests")
    op.drop_index(op.f("ix_retrieval_requests_branch_id"), table_name="retrieval_requests")
    op.drop_table("retrieval_requests")

    op.drop_index(op.f("ix_import_jobs_status"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_project_id"), table_name="import_jobs")
    op.drop_index(op.f("ix_import_jobs_branch_id"), table_name="import_jobs")
    op.drop_table("import_jobs")