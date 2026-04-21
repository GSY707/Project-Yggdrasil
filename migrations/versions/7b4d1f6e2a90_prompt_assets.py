"""prompt_assets

Revision ID: 7b4d1f6e2a90
Revises: 4f3fa0e1b9c3
Create Date: 2026-04-20 10:30:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "7b4d1f6e2a90"
down_revision = "4f3fa0e1b9c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "prompt_profile_versions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("prompt_profile_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("run_scope", sa.String(length=32), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_profile_versions")),
    )
    op.create_index(op.f("ix_prompt_profile_versions_content_hash"), "prompt_profile_versions", ["content_hash"], unique=False)
    op.create_index(op.f("ix_prompt_profile_versions_prompt_profile_id"), "prompt_profile_versions", ["prompt_profile_id"], unique=False)

    op.create_table(
        "seed_template_versions",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("seed_template_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("domain", sa.String(length=64), nullable=False),
        sa.Column("scenario", sa.String(length=255), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_seed_template_versions")),
    )
    op.create_index(op.f("ix_seed_template_versions_content_hash"), "seed_template_versions", ["content_hash"], unique=False)
    op.create_index(op.f("ix_seed_template_versions_scenario"), "seed_template_versions", ["scenario"], unique=False)
    op.create_index(op.f("ix_seed_template_versions_seed_template_id"), "seed_template_versions", ["seed_template_id"], unique=False)

    op.create_table(
        "prompt_compile_artifacts",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("model_invocation_id", sa.String(length=128), nullable=True),
        sa.Column("prompt_profile_version_id", sa.String(length=128), nullable=False),
        sa.Column("seed_template_version_id", sa.String(length=128), nullable=True),
        sa.Column("run_type", sa.String(length=32), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("scenario", sa.String(length=255), nullable=True),
        sa.Column("registered_tools", sa.JSON(), nullable=False),
        sa.Column("system_sections", sa.JSON(), nullable=False),
        sa.Column("user_sections", sa.JSON(), nullable=False),
        sa.Column("compiled_messages_ref", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_run_id"], ["agent_runs.id"], name=op.f("fk_prompt_compile_artifacts_agent_run_id_agent_runs"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["model_invocation_id"], ["model_invocations.id"], name=op.f("fk_prompt_compile_artifacts_model_invocation_id_model_invocations"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_prompt_compile_artifacts_project_id_projects"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prompt_profile_version_id"], ["prompt_profile_versions.id"], name=op.f("fk_prompt_compile_artifacts_prompt_profile_version_id_prompt_profile_versions"), ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["seed_template_version_id"], ["seed_template_versions.id"], name=op.f("fk_prompt_compile_artifacts_seed_template_version_id_seed_template_versions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_prompt_compile_artifacts_task_id_tasks"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_compile_artifacts")),
    )
    op.create_index(op.f("ix_prompt_compile_artifacts_agent_run_id"), "prompt_compile_artifacts", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_content_hash"), "prompt_compile_artifacts", ["content_hash"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_model_invocation_id"), "prompt_compile_artifacts", ["model_invocation_id"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_project_id"), "prompt_compile_artifacts", ["project_id"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_prompt_profile_version_id"), "prompt_compile_artifacts", ["prompt_profile_version_id"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_seed_template_version_id"), "prompt_compile_artifacts", ["seed_template_version_id"], unique=False)
    op.create_index(op.f("ix_prompt_compile_artifacts_task_id"), "prompt_compile_artifacts", ["task_id"], unique=False)

    with op.batch_alter_table("model_invocations", schema=None) as batch_op:
        batch_op.add_column(sa.Column("prompt_compile_artifact_id", sa.String(length=128), nullable=True))
        batch_op.create_index(batch_op.f("ix_model_invocations_prompt_compile_artifact_id"), ["prompt_compile_artifact_id"], unique=False)
        batch_op.create_foreign_key(
            batch_op.f("fk_model_invocations_prompt_compile_artifact_id_prompt_compile_artifacts"),
            "prompt_compile_artifacts",
            ["prompt_compile_artifact_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    with op.batch_alter_table("model_invocations", schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f("fk_model_invocations_prompt_compile_artifact_id_prompt_compile_artifacts"), type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_model_invocations_prompt_compile_artifact_id"))
        batch_op.drop_column("prompt_compile_artifact_id")

    op.drop_index(op.f("ix_prompt_compile_artifacts_task_id"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_seed_template_version_id"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_prompt_profile_version_id"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_project_id"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_model_invocation_id"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_content_hash"), table_name="prompt_compile_artifacts")
    op.drop_index(op.f("ix_prompt_compile_artifacts_agent_run_id"), table_name="prompt_compile_artifacts")
    op.drop_table("prompt_compile_artifacts")

    op.drop_index(op.f("ix_seed_template_versions_seed_template_id"), table_name="seed_template_versions")
    op.drop_index(op.f("ix_seed_template_versions_scenario"), table_name="seed_template_versions")
    op.drop_index(op.f("ix_seed_template_versions_content_hash"), table_name="seed_template_versions")
    op.drop_table("seed_template_versions")

    op.drop_index(op.f("ix_prompt_profile_versions_prompt_profile_id"), table_name="prompt_profile_versions")
    op.drop_index(op.f("ix_prompt_profile_versions_content_hash"), table_name="prompt_profile_versions")
    op.drop_table("prompt_profile_versions")
