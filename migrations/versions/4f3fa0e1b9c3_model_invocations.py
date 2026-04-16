"""model_invocations

Revision ID: 4f3fa0e1b9c3
Revises: 2c1d7a4fb0b2
Create Date: 2026-04-17 20:20:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "4f3fa0e1b9c3"
down_revision = "2c1d7a4fb0b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_invocations",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("route_decision_id", sa.String(length=128), nullable=True),
        sa.Column("requested_model", sa.String(length=255), nullable=False),
        sa.Column("requested_provider", sa.String(length=255), nullable=True),
        sa.Column("resolved_model", sa.String(length=255), nullable=False),
        sa.Column("resolved_provider", sa.String(length=255), nullable=True),
        sa.Column("invocation_kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("trace_id", sa.String(length=128), nullable=True),
        sa.Column("request_ref", sa.JSON(), nullable=True),
        sa.Column("response_ref", sa.JSON(), nullable=True),
        sa.Column("input_tokens_used", sa.Integer(), nullable=False),
        sa.Column("output_tokens_used", sa.Integer(), nullable=False),
        sa.Column("cost_used", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_model_invocations_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_model_invocations_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["route_decision_id"], ["model_route_decisions.id"], name=op.f("fk_model_invocations_route_decision_id_model_route_decisions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_model_invocations_task_id_tasks"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_invocations")),
    )
    op.create_index(op.f("ix_model_invocations_agent_run_id"), "model_invocations", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_model_invocations_project_id"), "model_invocations", ["project_id"], unique=False)
    op.create_index(op.f("ix_model_invocations_route_decision_id"), "model_invocations", ["route_decision_id"], unique=False)
    op.create_index(op.f("ix_model_invocations_status"), "model_invocations", ["status"], unique=False)
    op.create_index(op.f("ix_model_invocations_task_id"), "model_invocations", ["task_id"], unique=False)
    op.create_index(op.f("ix_model_invocations_trace_id"), "model_invocations", ["trace_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_invocations_trace_id"), table_name="model_invocations")
    op.drop_index(op.f("ix_model_invocations_task_id"), table_name="model_invocations")
    op.drop_index(op.f("ix_model_invocations_status"), table_name="model_invocations")
    op.drop_index(op.f("ix_model_invocations_route_decision_id"), table_name="model_invocations")
    op.drop_index(op.f("ix_model_invocations_project_id"), table_name="model_invocations")
    op.drop_index(op.f("ix_model_invocations_agent_run_id"), table_name="model_invocations")
    op.drop_table("model_invocations")