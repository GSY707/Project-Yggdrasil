"""agent_run_fork_fields

Revision ID: c2f4b8a91d63
Revises: 9c0a7d6e5f21
Create Date: 2026-06-21 00:00:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c2f4b8a91d63"
down_revision = "9c0a7d6e5f21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.add_column(sa.Column("fork_root_run_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("fork_depth", sa.Integer(), nullable=False, server_default=sa.text("0")))
        batch_op.add_column(sa.Column("assigned_work_tree_node_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("parent_context_anchor", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("fork_group_id", sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f("ix_agent_runs_fork_root_run_id"), ["fork_root_run_id"], unique=False)
        batch_op.create_index(
            batch_op.f("ix_agent_runs_assigned_work_tree_node_id"),
            ["assigned_work_tree_node_id"],
            unique=False,
        )
        batch_op.create_index(batch_op.f("ix_agent_runs_fork_group_id"), ["fork_group_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index(batch_op.f("ix_agent_runs_fork_group_id"))
        batch_op.drop_index(batch_op.f("ix_agent_runs_assigned_work_tree_node_id"))
        batch_op.drop_index(batch_op.f("ix_agent_runs_fork_root_run_id"))
        batch_op.drop_column("fork_group_id")
        batch_op.drop_column("parent_context_anchor")
        batch_op.drop_column("assigned_work_tree_node_id")
        batch_op.drop_column("fork_depth")
        batch_op.drop_column("fork_root_run_id")
