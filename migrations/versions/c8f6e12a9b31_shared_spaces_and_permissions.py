"""shared_spaces_and_permissions

Revision ID: c8f6e12a9b31
Revises: 7b4d1f6e2a90
Create Date: 2026-04-20 12:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c8f6e12a9b31"
down_revision = "7b4d1f6e2a90"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "space_mounts",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("host_space_id", sa.String(length=128), nullable=False),
        sa.Column("mounted_space_id", sa.String(length=128), nullable=False),
        sa.Column("mount_mode", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["host_space_id"], ["spaces.id"], name=op.f("fk_space_mounts_host_space_id_spaces"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mounted_space_id"], ["spaces.id"], name=op.f("fk_space_mounts_mounted_space_id_spaces"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_space_mounts_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_space_mounts")),
    )
    op.create_index(op.f("ix_space_mounts_host_space_id"), "space_mounts", ["host_space_id"], unique=False)
    op.create_index(op.f("ix_space_mounts_mounted_space_id"), "space_mounts", ["mounted_space_id"], unique=False)
    op.create_index(op.f("ix_space_mounts_project_id"), "space_mounts", ["project_id"], unique=False)
    op.create_index(op.f("ix_space_mounts_status"), "space_mounts", ["status"], unique=False)

    op.create_table(
        "permission_tuples",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("relation", sa.String(length=128), nullable=False),
        sa.Column("resource", sa.String(length=255), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=True),
        sa.Column("effect", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_permission_tuples_project_id_projects"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_permission_tuples")),
    )
    op.create_index(op.f("ix_permission_tuples_effect"), "permission_tuples", ["effect"], unique=False)
    op.create_index(op.f("ix_permission_tuples_project_id"), "permission_tuples", ["project_id"], unique=False)
    op.create_index(op.f("ix_permission_tuples_relation"), "permission_tuples", ["relation"], unique=False)
    op.create_index(op.f("ix_permission_tuples_resource"), "permission_tuples", ["resource"], unique=False)
    op.create_index(op.f("ix_permission_tuples_subject"), "permission_tuples", ["subject"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_permission_tuples_subject"), table_name="permission_tuples")
    op.drop_index(op.f("ix_permission_tuples_resource"), table_name="permission_tuples")
    op.drop_index(op.f("ix_permission_tuples_relation"), table_name="permission_tuples")
    op.drop_index(op.f("ix_permission_tuples_project_id"), table_name="permission_tuples")
    op.drop_index(op.f("ix_permission_tuples_effect"), table_name="permission_tuples")
    op.drop_table("permission_tuples")

    op.drop_index(op.f("ix_space_mounts_status"), table_name="space_mounts")
    op.drop_index(op.f("ix_space_mounts_project_id"), table_name="space_mounts")
    op.drop_index(op.f("ix_space_mounts_mounted_space_id"), table_name="space_mounts")
    op.drop_index(op.f("ix_space_mounts_host_space_id"), table_name="space_mounts")
    op.drop_table("space_mounts")