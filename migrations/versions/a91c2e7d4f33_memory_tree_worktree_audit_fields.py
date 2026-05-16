"""memory_tree_worktree_audit_fields

Revision ID: a91c2e7d4f33
Revises: 2c1d7a4fb0b2, d41f9c3b7e12, f2a1c4d9e5b7
Create Date: 2026-05-16 23:20:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "a91c2e7d4f33"
down_revision = ("2c1d7a4fb0b2", "d41f9c3b7e12", "f2a1c4d9e5b7")
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("nodes") as batch_op:
        batch_op.add_column(sa.Column("window_index", sa.Integer(), nullable=False, server_default=sa.text("1")))
        batch_op.add_column(sa.Column("source_work_tree_node_id", sa.String(length=128), nullable=True))
        batch_op.create_index(op.f("ix_nodes_source_work_tree_node_id"), ["source_work_tree_node_id"], unique=False)

    with op.batch_alter_table("retrieval_requests") as batch_op:
        batch_op.add_column(sa.Column("reverse_trace_mode", sa.Boolean(), nullable=False, server_default=sa.text("false")))
        batch_op.add_column(sa.Column("work_tree_node_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("window_index", sa.Integer(), nullable=True))
        batch_op.create_index(op.f("ix_retrieval_requests_work_tree_node_id"), ["work_tree_node_id"], unique=False)

    with op.batch_alter_table("model_invocations") as batch_op:
        batch_op.add_column(sa.Column("output_labels", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
        batch_op.add_column(sa.Column("assistant_text_summary", sa.Text(), nullable=True))

    with op.batch_alter_table("assets") as batch_op:
        batch_op.add_column(sa.Column("related_work_tree_node_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.add_column(sa.Column("work_tree_snapshot", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("takeover_protocol_snapshot", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.drop_column("takeover_protocol_snapshot")
        batch_op.drop_column("work_tree_snapshot")

    with op.batch_alter_table("assets") as batch_op:
        batch_op.drop_column("related_work_tree_node_ids")

    with op.batch_alter_table("model_invocations") as batch_op:
        batch_op.drop_column("assistant_text_summary")
        batch_op.drop_column("output_labels")

    with op.batch_alter_table("retrieval_requests") as batch_op:
        batch_op.drop_index(op.f("ix_retrieval_requests_work_tree_node_id"))
        batch_op.drop_column("window_index")
        batch_op.drop_column("work_tree_node_id")
        batch_op.drop_column("reverse_trace_mode")

    with op.batch_alter_table("nodes") as batch_op:
        batch_op.drop_index(op.f("ix_nodes_source_work_tree_node_id"))
        batch_op.drop_column("source_work_tree_node_id")
        batch_op.drop_column("window_index")