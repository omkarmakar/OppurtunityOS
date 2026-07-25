"""Create scheduler_state table.

Revision ID: 009
Revises: 008
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: str = "008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "scheduler_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("task_name", sa.String(100), nullable=False),
        # Local calendar date the task last ran successfully.
        sa.Column("last_run_date", sa.Date(), nullable=True),
        # UTC timestamp of the last successful run (for diagnostics).
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "task_name", name="uq_scheduler_state_user_task"),
    )
    op.create_index(
        op.f("ix_scheduler_state_user_id"), "scheduler_state", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_scheduler_state_user_id"), table_name="scheduler_state")
    op.drop_table("scheduler_state")
