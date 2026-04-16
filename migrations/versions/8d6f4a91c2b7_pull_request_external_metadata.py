"""pull_request_external_metadata

Revision ID: 8d6f4a91c2b7
Revises: e7a4c55d7d4b
Create Date: 2026-04-17 00:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "8d6f4a91c2b7"
down_revision = "e7a4c55d7d4b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("pull_requests", sa.Column("external_id", sa.String(length=128), nullable=True))
    op.add_column("pull_requests", sa.Column("external_url", sa.String(length=512), nullable=True))
    op.add_column("pull_requests", sa.Column("merge_commit_ref", sa.String(length=255), nullable=True))
    op.create_index(op.f("ix_pull_requests_external_id"), "pull_requests", ["external_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_pull_requests_external_id"), table_name="pull_requests")
    op.drop_column("pull_requests", "merge_commit_ref")
    op.drop_column("pull_requests", "external_url")
    op.drop_column("pull_requests", "external_id")