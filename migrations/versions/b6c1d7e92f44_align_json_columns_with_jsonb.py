"""align_json_columns_with_jsonb

Revision ID: b6c1d7e92f44
Revises: 9e2c7b1a4d55
Create Date: 2026-05-01 10:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b6c1d7e92f44"
down_revision = "9e2c7b1a4d55"
branch_labels = None
depends_on = None


JSON_TYPE = postgresql.JSON(astext_type=sa.Text())
JSONB_TYPE = postgresql.JSONB(astext_type=sa.Text())
JSONB_COLUMNS = [
    ("asset_embeddings", "vector_ref"),
    ("assets", "source_ref"),
    ("assets", "created_by"),
    ("dataset_versions", "source_filter"),
    ("evaluation_runs", "metrics_ref"),
    ("evaluation_suites", "metric_refs"),
    ("model_artifacts", "metrics_ref"),
    ("model_invocations", "request_ref"),
    ("model_invocations", "response_ref"),
    ("permission_tuples", "condition"),
    ("permission_tuples", "created_by"),
    ("prompt_compile_artifacts", "registered_tools"),
    ("prompt_compile_artifacts", "system_sections"),
    ("prompt_compile_artifacts", "user_sections"),
    ("prompt_compile_artifacts", "compiled_messages_ref"),
    ("prompt_profile_versions", "body"),
    ("seed_template_versions", "body"),
    ("space_mounts", "created_by"),
]


def _alter_json_type(table_name: str, column_name: str, *, target_type: sa.types.TypeEngine, using_suffix: str) -> None:
    op.alter_column(
        table_name,
        column_name,
        existing_type=JSON_TYPE,
        type_=target_type,
        postgresql_using=f"{column_name}::{using_suffix}",
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name, column_name in JSONB_COLUMNS:
        _alter_json_type(table_name, column_name, target_type=JSONB_TYPE, using_suffix="jsonb")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table_name, column_name in JSONB_COLUMNS:
        _alter_json_type(table_name, column_name, target_type=JSON_TYPE, using_suffix="json")