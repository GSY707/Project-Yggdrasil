"""task_snapshot_runtime_pointer_fields

Revision ID: 5f7c2e9a1b44
Revises: 1e3a7b8c9d01
Create Date: 2026-05-24 10:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "5f7c2e9a1b44"
down_revision = "1e3a7b8c9d01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.add_column(sa.Column("current_node_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("working_node_annotation", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("pc_memo", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("top_frame_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("stack_digest", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.drop_column("stack_digest")
        batch_op.drop_column("top_frame_id")
        batch_op.drop_column("pc_memo")
        batch_op.drop_column("working_node_annotation")
        batch_op.drop_column("current_node_id")