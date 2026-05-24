"""runtime_mailbox_side_channel_tables

Revision ID: 7ad7d9b8c4f1
Revises: 6c4e1f2b8a77
Create Date: 2026-05-24 22:45:00.000000

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "7ad7d9b8c4f1"
down_revision = "6c4e1f2b8a77"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mailbox_messages",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("sender", sa.JSON(), nullable=False),
        sa.Column("message_kind", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("work_tree_node_id", sa.String(length=128), nullable=True),
        sa.Column("wake_on_message", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("payload_ref", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_mailbox_messages_agent_run_id_agent_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_mailbox_messages_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_mailbox_messages_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_mailbox_messages")),
    )
    op.create_index(op.f("ix_mailbox_messages_agent_run_id"), "mailbox_messages", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_mailbox_messages_message_kind"), "mailbox_messages", ["message_kind"], unique=False)
    op.create_index(op.f("ix_mailbox_messages_project_id"), "mailbox_messages", ["project_id"], unique=False)
    op.create_index(op.f("ix_mailbox_messages_status"), "mailbox_messages", ["status"], unique=False)
    op.create_index(op.f("ix_mailbox_messages_task_id"), "mailbox_messages", ["task_id"], unique=False)
    op.create_index(op.f("ix_mailbox_messages_work_tree_node_id"), "mailbox_messages", ["work_tree_node_id"], unique=False)
    op.create_index(
        "ix_mailbox_messages_task_status_created",
        "mailbox_messages",
        ["task_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "side_channel_events",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("project_id", sa.String(length=128), nullable=False),
        sa.Column("task_id", sa.String(length=128), nullable=False),
        sa.Column("agent_run_id", sa.String(length=128), nullable=True),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("event_kind", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("work_tree_node_id", sa.String(length=128), nullable=True),
        sa.Column("payload_ref", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_side_channel_events_agent_run_id_agent_runs"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_side_channel_events_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
            name=op.f("fk_side_channel_events_task_id_tasks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_side_channel_events")),
    )
    op.create_index(op.f("ix_side_channel_events_agent_run_id"), "side_channel_events", ["agent_run_id"], unique=False)
    op.create_index(op.f("ix_side_channel_events_event_kind"), "side_channel_events", ["event_kind"], unique=False)
    op.create_index(op.f("ix_side_channel_events_level"), "side_channel_events", ["level"], unique=False)
    op.create_index(op.f("ix_side_channel_events_project_id"), "side_channel_events", ["project_id"], unique=False)
    op.create_index(op.f("ix_side_channel_events_task_id"), "side_channel_events", ["task_id"], unique=False)
    op.create_index(op.f("ix_side_channel_events_work_tree_node_id"), "side_channel_events", ["work_tree_node_id"], unique=False)
    op.create_index(
        "ix_side_channel_events_task_created",
        "side_channel_events",
        ["task_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_side_channel_events_task_created", table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_work_tree_node_id"), table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_task_id"), table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_project_id"), table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_level"), table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_event_kind"), table_name="side_channel_events")
    op.drop_index(op.f("ix_side_channel_events_agent_run_id"), table_name="side_channel_events")
    op.drop_table("side_channel_events")

    op.drop_index("ix_mailbox_messages_task_status_created", table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_work_tree_node_id"), table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_task_id"), table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_status"), table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_project_id"), table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_message_kind"), table_name="mailbox_messages")
    op.drop_index(op.f("ix_mailbox_messages_agent_run_id"), table_name="mailbox_messages")
    op.drop_table("mailbox_messages")