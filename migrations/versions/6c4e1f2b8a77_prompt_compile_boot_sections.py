"""prompt_compile_boot_sections

Revision ID: 6c4e1f2b8a77
Revises: 5f7c2e9a1b44
Create Date: 2026-05-24 13:40:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "6c4e1f2b8a77"
down_revision = "5f7c2e9a1b44"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "boot_sections",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("prompt_compile_artifacts") as batch_op:
        batch_op.drop_column("boot_sections")
