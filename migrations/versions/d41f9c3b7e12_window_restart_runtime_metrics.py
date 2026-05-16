"""window_restart_runtime_metrics

Revision ID: d41f9c3b7e12
Revises: b6c1d7e92f44
Create Date: 2026-05-16 16:20:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d41f9c3b7e12"
down_revision = "b6c1d7e92f44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("window_index", sa.Integer(), nullable=False, server_default=sa.text("1")))
        batch_op.add_column(sa.Column("restart_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("cumulative_window_span_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("carry_forward_loss_count", sa.Integer(), nullable=False, server_default=sa.text("0")))

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("window_index", sa.Integer(), nullable=False, server_default=sa.text("1")))
        batch_op.add_column(sa.Column("restart_count", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("cumulative_window_span_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")))


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_column("cumulative_window_span_tokens")
        batch_op.drop_column("restart_count")
        batch_op.drop_column("window_index")

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("carry_forward_loss_count")
        batch_op.drop_column("cumulative_window_span_tokens")
        batch_op.drop_column("restart_count")
        batch_op.drop_column("window_index")