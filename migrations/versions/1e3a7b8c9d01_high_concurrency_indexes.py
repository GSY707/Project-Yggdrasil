"""high concurrency table indexes

Revision ID: 1e3a7b8c9d01
Revises: a91c2e7d4f33
Create Date: 2026-05-17 21:15:00

"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "1e3a7b8c9d01"
down_revision = "a91c2e7d4f33"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_nodes_branch_created_at", "nodes", ["branch_id", "created_at"], unique=False)
    op.create_index(
        "ix_import_fragments_job_created",
        "import_fragments",
        ["import_job_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_snapshots_task_status_created",
        "task_snapshots",
        ["task_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_task_snapshots_task_created",
        "task_snapshots",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_model_invocations_task_created",
        "model_invocations",
        ["task_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_model_invocations_run_created",
        "model_invocations",
        ["agent_run_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_model_invocations_run_created", table_name="model_invocations")
    op.drop_index("ix_model_invocations_task_created", table_name="model_invocations")
    op.drop_index("ix_task_snapshots_task_created", table_name="task_snapshots")
    op.drop_index("ix_task_snapshots_task_status_created", table_name="task_snapshots")
    op.drop_index("ix_import_fragments_job_created", table_name="import_fragments")
    op.drop_index("ix_nodes_branch_created_at", table_name="nodes")
