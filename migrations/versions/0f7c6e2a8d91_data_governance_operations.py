"""data_governance_operations

Revision ID: 0f7c6e2a8d91
Revises: 7ad7d9b8c4f1
Create Date: 2026-06-05 23:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0f7c6e2a8d91"
down_revision = "7ad7d9b8c4f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "data_governance_operations",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("operation_type", sa.String(length=64), nullable=False),
        sa.Column("scope_kind", sa.String(length=64), nullable=False),
        sa.Column("scope_id", sa.String(length=128), nullable=True),
        sa.Column("dry_run", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("plan_ref", sa.JSON(), nullable=True),
        sa.Column("result_ref", sa.JSON(), nullable=True),
        sa.Column("requested_by", sa.JSON(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_data_governance_operations")),
    )
    op.create_index(op.f("ix_data_governance_operations_dry_run"), "data_governance_operations", ["dry_run"], unique=False)
    op.create_index(op.f("ix_data_governance_operations_operation_type"), "data_governance_operations", ["operation_type"], unique=False)
    op.create_index(op.f("ix_data_governance_operations_scope_id"), "data_governance_operations", ["scope_id"], unique=False)
    op.create_index(op.f("ix_data_governance_operations_scope_kind"), "data_governance_operations", ["scope_kind"], unique=False)
    op.create_index(op.f("ix_data_governance_operations_status"), "data_governance_operations", ["status"], unique=False)
    op.create_index(
        "ix_data_governance_scope_created",
        "data_governance_operations",
        ["scope_kind", "scope_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_data_governance_scope_created", table_name="data_governance_operations")
    op.drop_index(op.f("ix_data_governance_operations_status"), table_name="data_governance_operations")
    op.drop_index(op.f("ix_data_governance_operations_scope_kind"), table_name="data_governance_operations")
    op.drop_index(op.f("ix_data_governance_operations_scope_id"), table_name="data_governance_operations")
    op.drop_index(op.f("ix_data_governance_operations_operation_type"), table_name="data_governance_operations")
    op.drop_index(op.f("ix_data_governance_operations_dry_run"), table_name="data_governance_operations")
    op.drop_table("data_governance_operations")
