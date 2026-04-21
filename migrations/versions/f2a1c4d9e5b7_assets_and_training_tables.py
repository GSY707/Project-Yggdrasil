"""assets_and_training_tables

Revision ID: f2a1c4d9e5b7
Revises: c8f6e12a9b31
Create Date: 2026-04-20 15:10:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f2a1c4d9e5b7"
down_revision = "c8f6e12a9b31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("space_id", sa.String(length=128), nullable=False),
        sa.Column("branch_id", sa.String(length=128), nullable=False),
        sa.Column("owner_node_id", sa.String(length=128), nullable=True),
        sa.Column("media_type", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("source_ref", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["branch_id"], ["memory_branches.id"], name=op.f("fk_assets_branch_id_memory_branches"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_node_id"], ["nodes.id"], name=op.f("fk_assets_owner_node_id_nodes"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_assets_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["space_id"], ["spaces.id"], name=op.f("fk_assets_space_id_spaces"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
    )
    op.create_index(op.f("ix_assets_project_id"), "assets", ["project_id"], unique=False)
    op.create_index(op.f("ix_assets_space_id"), "assets", ["space_id"], unique=False)
    op.create_index(op.f("ix_assets_branch_id"), "assets", ["branch_id"], unique=False)
    op.create_index(op.f("ix_assets_owner_node_id"), "assets", ["owner_node_id"], unique=False)
    op.create_index(op.f("ix_assets_media_type"), "assets", ["media_type"], unique=False)
    op.create_index(op.f("ix_assets_role"), "assets", ["role"], unique=False)
    op.create_index(op.f("ix_assets_checksum"), "assets", ["checksum"], unique=False)

    op.create_table(
        "asset_segments",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("asset_id", sa.String(length=128), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=False),
        sa.Column("end_offset", sa.Integer(), nullable=False),
        sa.Column("text_excerpt", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("embedding_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], name=op.f("fk_asset_segments_asset_id_assets"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_segments")),
        sa.UniqueConstraint("asset_id", "ordinal", name=op.f("uq_asset_segments_asset_id")),
    )
    op.create_index(op.f("ix_asset_segments_asset_id"), "asset_segments", ["asset_id"], unique=False)
    op.create_index(op.f("ix_asset_segments_embedding_id"), "asset_segments", ["embedding_id"], unique=False)

    op.create_table(
        "asset_embeddings",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("owner_kind", sa.String(length=32), nullable=False),
        sa.Column("owner_id", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("vector_ref", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_embeddings")),
    )
    op.create_index(op.f("ix_asset_embeddings_owner_kind"), "asset_embeddings", ["owner_kind"], unique=False)
    op.create_index(op.f("ix_asset_embeddings_owner_id"), "asset_embeddings", ["owner_id"], unique=False)

    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("dataset_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("source_filter", sa.JSON(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dataset_versions")),
        sa.UniqueConstraint("dataset_name", "version", name=op.f("uq_dataset_versions_dataset_name")),
    )
    op.create_index(op.f("ix_dataset_versions_dataset_name"), "dataset_versions", ["dataset_name"], unique=False)

    op.create_table(
        "model_artifacts",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("base_model", sa.String(length=255), nullable=False),
        sa.Column("tuning_method", sa.String(length=32), nullable=False),
        sa.Column("dataset_version_id", sa.String(length=128), nullable=False),
        sa.Column("metrics_ref", sa.JSON(), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["dataset_version_id"], ["dataset_versions.id"], name=op.f("fk_model_artifacts_dataset_version_id_dataset_versions"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_artifacts")),
    )
    op.create_index(op.f("ix_model_artifacts_base_model"), "model_artifacts", ["base_model"], unique=False)
    op.create_index(op.f("ix_model_artifacts_tuning_method"), "model_artifacts", ["tuning_method"], unique=False)
    op.create_index(op.f("ix_model_artifacts_dataset_version_id"), "model_artifacts", ["dataset_version_id"], unique=False)
    op.create_index(op.f("ix_model_artifacts_status"), "model_artifacts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_model_artifacts_status"), table_name="model_artifacts")
    op.drop_index(op.f("ix_model_artifacts_dataset_version_id"), table_name="model_artifacts")
    op.drop_index(op.f("ix_model_artifacts_tuning_method"), table_name="model_artifacts")
    op.drop_index(op.f("ix_model_artifacts_base_model"), table_name="model_artifacts")
    op.drop_table("model_artifacts")

    op.drop_index(op.f("ix_dataset_versions_dataset_name"), table_name="dataset_versions")
    op.drop_table("dataset_versions")

    op.drop_index(op.f("ix_asset_embeddings_owner_id"), table_name="asset_embeddings")
    op.drop_index(op.f("ix_asset_embeddings_owner_kind"), table_name="asset_embeddings")
    op.drop_table("asset_embeddings")

    op.drop_index(op.f("ix_asset_segments_embedding_id"), table_name="asset_segments")
    op.drop_index(op.f("ix_asset_segments_asset_id"), table_name="asset_segments")
    op.drop_table("asset_segments")

    op.drop_index(op.f("ix_assets_checksum"), table_name="assets")
    op.drop_index(op.f("ix_assets_role"), table_name="assets")
    op.drop_index(op.f("ix_assets_media_type"), table_name="assets")
    op.drop_index(op.f("ix_assets_owner_node_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_branch_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_space_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_project_id"), table_name="assets")
    op.drop_table("assets")