"""durable_task_resume_chain

Revision ID: 9c0a7d6e5f21
Revises: 0f7c6e2a8d91, d41f9c3b7e12
Create Date: 2026-06-19 10:00:00.000000

"""
from __future__ import annotations

from hashlib import sha256

from alembic import op
import sqlalchemy as sa


revision = "9c0a7d6e5f21"
down_revision = ("0f7c6e2a8d91", "d41f9c3b7e12")
branch_labels = None
depends_on = None


def _hash_resume_token(value: str | None) -> str | None:
    token = str(value or "").strip()
    if not token:
        return None
    return sha256(token.encode("utf-8")).hexdigest()


def upgrade() -> None:
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("active_resume_attempt_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("resume_blocked_reason", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pending_control_intent", sa.String(length=64), nullable=True))

    op.execute(
        sa.text(
            "UPDATE tasks "
            "SET status = 'running', pending_control_intent = 'pause', pause_requested = TRUE "
            "WHERE status = 'pause-requested'"
        )
    )

    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.alter_column("agent_run_id", existing_type=sa.String(length=128), nullable=True)
        batch_op.add_column(sa.Column("retention_class", sa.String(length=32), nullable=False, server_default=sa.text("'active-paused'")))
        batch_op.add_column(sa.Column("schema_version", sa.String(length=64), nullable=False, server_default=sa.text("'task-snapshot.v1'")))
        batch_op.add_column(
            sa.Column(
                "runtime_contract_version",
                sa.String(length=128),
                nullable=False,
                server_default=sa.text("'task-pause-resume-continuation-contract-v0.1'"),
            )
        )
        batch_op.add_column(sa.Column("storage_manifest_ref", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("manifest_checksum", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("resume_token_hash", sa.String(length=128), nullable=True))
        batch_op.alter_column("resume_token", existing_type=sa.String(length=255), nullable=True)
        batch_op.add_column(sa.Column("blocker_code", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("blocker_message", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("saved_label", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("saved_by_user_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("leased_until", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("superseded_by_snapshot_id", sa.String(length=128), nullable=True))

    bind = op.get_bind()
    snapshots = sa.table(
        "task_snapshots",
        sa.column("id", sa.String()),
        sa.column("resume_token", sa.String()),
        sa.column("resume_token_hash", sa.String()),
    )
    for row in bind.execute(sa.select(snapshots.c.id, snapshots.c.resume_token)):
        resume_token_hash = _hash_resume_token(row.resume_token)
        if resume_token_hash is not None:
            bind.execute(
                snapshots.update()
                .where(snapshots.c.id == row.id)
                .values(resume_token_hash=resume_token_hash)
            )

    op.create_index(op.f("ix_task_snapshots_resume_token_hash"), "task_snapshots", ["resume_token_hash"], unique=False)

    op.create_table(
        "task_resume_attempts",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("requested_by", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocker_code", sa.String(length=128), nullable=True),
        sa.Column("blocker_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["snapshot_id"], ["task_snapshots.id"], name=op.f("fk_task_resume_attempts_snapshot_id_task_snapshots"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_task_resume_attempts_task_id_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_resume_attempts")),
    )
    op.create_index(op.f("ix_task_resume_attempts_snapshot_id"), "task_resume_attempts", ["snapshot_id"], unique=False)
    op.create_index(op.f("ix_task_resume_attempts_status"), "task_resume_attempts", ["status"], unique=False)
    op.create_index(op.f("ix_task_resume_attempts_task_id"), "task_resume_attempts", ["task_id"], unique=False)
    op.create_index("ix_task_resume_attempts_task_status_created", "task_resume_attempts", ["task_id", "status", "created_at"], unique=False)
    op.create_index("ix_task_resume_attempts_snapshot", "task_resume_attempts", ["snapshot_id"], unique=False)

    op.create_table(
        "runtime_work_items",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("queue", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=True),
        sa.Column("activity", sa.String(length=128), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_runtime_work_items_task_id_tasks"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_runtime_work_items")),
    )
    op.create_index(op.f("ix_runtime_work_items_queue"), "runtime_work_items", ["queue"], unique=False)
    op.create_index(op.f("ix_runtime_work_items_status"), "runtime_work_items", ["status"], unique=False)
    op.create_index(op.f("ix_runtime_work_items_task_id"), "runtime_work_items", ["task_id"], unique=False)
    op.create_index("ix_runtime_work_items_queue_status_created", "runtime_work_items", ["queue", "status", "created_at"], unique=False)
    op.create_index("ix_runtime_work_items_task_status", "runtime_work_items", ["task_id", "status"], unique=False)

    op.create_table(
        "task_branches",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("parent_task_id", sa.String(length=128), nullable=False),
        sa.Column("child_task_id", sa.String(length=128), nullable=False),
        sa.Column("source_snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("source_snapshot_checksum", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["child_task_id"], ["tasks.id"], name=op.f("fk_task_branches_child_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_task_id"], ["tasks.id"], name=op.f("fk_task_branches_parent_task_id_tasks"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_snapshot_id"], ["task_snapshots.id"], name=op.f("fk_task_branches_source_snapshot_id_task_snapshots"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_branches")),
    )
    op.create_index(op.f("ix_task_branches_child_task_id"), "task_branches", ["child_task_id"], unique=False)
    op.create_index(op.f("ix_task_branches_parent_task_id"), "task_branches", ["parent_task_id"], unique=False)
    op.create_index(op.f("ix_task_branches_source_snapshot_id"), "task_branches", ["source_snapshot_id"], unique=False)
    op.create_index("ix_task_branches_parent_created", "task_branches", ["parent_task_id", "created_at"], unique=False)
    op.create_index("ix_task_branches_child", "task_branches", ["child_task_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_branches_child", table_name="task_branches")
    op.drop_index("ix_task_branches_parent_created", table_name="task_branches")
    op.drop_index(op.f("ix_task_branches_source_snapshot_id"), table_name="task_branches")
    op.drop_index(op.f("ix_task_branches_parent_task_id"), table_name="task_branches")
    op.drop_index(op.f("ix_task_branches_child_task_id"), table_name="task_branches")
    op.drop_table("task_branches")

    op.drop_index("ix_runtime_work_items_task_status", table_name="runtime_work_items")
    op.drop_index("ix_runtime_work_items_queue_status_created", table_name="runtime_work_items")
    op.drop_index(op.f("ix_runtime_work_items_task_id"), table_name="runtime_work_items")
    op.drop_index(op.f("ix_runtime_work_items_status"), table_name="runtime_work_items")
    op.drop_index(op.f("ix_runtime_work_items_queue"), table_name="runtime_work_items")
    op.drop_table("runtime_work_items")

    op.drop_index("ix_task_resume_attempts_snapshot", table_name="task_resume_attempts")
    op.drop_index("ix_task_resume_attempts_task_status_created", table_name="task_resume_attempts")
    op.drop_index(op.f("ix_task_resume_attempts_task_id"), table_name="task_resume_attempts")
    op.drop_index(op.f("ix_task_resume_attempts_status"), table_name="task_resume_attempts")
    op.drop_index(op.f("ix_task_resume_attempts_snapshot_id"), table_name="task_resume_attempts")
    op.drop_table("task_resume_attempts")

    op.drop_index(op.f("ix_task_snapshots_resume_token_hash"), table_name="task_snapshots")
    with op.batch_alter_table("task_snapshots") as batch_op:
        batch_op.drop_column("superseded_by_snapshot_id")
        batch_op.drop_column("leased_until")
        batch_op.drop_column("verified_at")
        batch_op.drop_column("expires_at")
        batch_op.drop_column("saved_by_user_id")
        batch_op.drop_column("saved_label")
        batch_op.drop_column("blocker_message")
        batch_op.drop_column("blocker_code")
        batch_op.alter_column("resume_token", existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column("resume_token_hash")
        batch_op.drop_column("manifest_checksum")
        batch_op.drop_column("storage_manifest_ref")
        batch_op.drop_column("runtime_contract_version")
        batch_op.drop_column("schema_version")
        batch_op.drop_column("retention_class")
        batch_op.alter_column("agent_run_id", existing_type=sa.String(length=128), nullable=False)

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_column("pending_control_intent")
        batch_op.drop_column("resume_blocked_reason")
        batch_op.drop_column("active_resume_attempt_id")
