"""evaluation_tables

Revision ID: 2c1d7a4fb0b2
Revises: 8d6f4a91c2b7
Create Date: 2026-04-17 09:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "2c1d7a4fb0b2"
down_revision = "8d6f4a91c2b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "evaluation_suites",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=32), nullable=False),
        sa.Column("metric_refs", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_suites")),
    )
    op.create_index(op.f("ix_evaluation_suites_domain"), "evaluation_suites", ["domain"], unique=False)

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("suite_id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject_kind", sa.String(length=64), nullable=False),
        sa.Column("subject_ref", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics_ref", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_evaluation_runs_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["suite_id"], ["evaluation_suites.id"], name=op.f("fk_evaluation_runs_suite_id_evaluation_suites"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evaluation_runs")),
    )
    op.create_index(op.f("ix_evaluation_runs_project_id"), "evaluation_runs", ["project_id"], unique=False)
    op.create_index(op.f("ix_evaluation_runs_status"), "evaluation_runs", ["status"], unique=False)
    op.create_index(op.f("ix_evaluation_runs_suite_id"), "evaluation_runs", ["suite_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_evaluation_runs_suite_id"), table_name="evaluation_runs")
    op.drop_index(op.f("ix_evaluation_runs_status"), table_name="evaluation_runs")
    op.drop_index(op.f("ix_evaluation_runs_project_id"), table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    op.drop_index(op.f("ix_evaluation_suites_domain"), table_name="evaluation_suites")
    op.drop_table("evaluation_suites")