"""app_scope_for_runtime_records

Revision ID: 9e2c7b1a4d55
Revises: f2a1c4d9e5b7
Create Date: 2026-04-21 09:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "9e2c7b1a4d55"
down_revision = "f2a1c4d9e5b7"
branch_labels = None
depends_on = None


DEFAULT_APP_ID = "yggdrasil.app.base"


def upgrade() -> None:
    default_expr = sa.text(f"'{DEFAULT_APP_ID}'")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("app_id", sa.String(length=255), nullable=False, server_default=default_expr))
        batch_op.create_index(batch_op.f("ix_tasks_app_id"), ["app_id"], unique=False)

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("app_id", sa.String(length=255), nullable=False, server_default=default_expr))
        batch_op.create_index(batch_op.f("ix_agent_runs_app_id"), ["app_id"], unique=False)

    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.add_column(sa.Column("app_id", sa.String(length=255), nullable=False, server_default=default_expr))
        batch_op.create_index(batch_op.f("ix_task_snapshots_app_id"), ["app_id"], unique=False)

    with op.batch_alter_table("model_invocations") as batch_op:
        batch_op.add_column(sa.Column("app_id", sa.String(length=255), nullable=False, server_default=default_expr))
        batch_op.create_index(batch_op.f("ix_model_invocations_app_id"), ["app_id"], unique=False)

    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.add_column(sa.Column("app_id", sa.String(length=255), nullable=False, server_default=default_expr))
        batch_op.create_index(batch_op.f("ix_prompt_compile_artifacts_app_id"), ["app_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.drop_index(batch_op.f("ix_prompt_compile_artifacts_app_id"))
        batch_op.drop_column("app_id")

    with op.batch_alter_table("model_invocations") as batch_op:
        batch_op.drop_index(batch_op.f("ix_model_invocations_app_id"))
        batch_op.drop_column("app_id")

    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.drop_index(batch_op.f("ix_task_snapshots_app_id"))
        batch_op.drop_column("app_id")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_runs_app_id"))
        batch_op.drop_column("app_id")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index(batch_op.f("ix_tasks_app_id"))
        batch_op.drop_column("app_id")