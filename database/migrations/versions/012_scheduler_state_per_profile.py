"""SchedulerState — add nullable profile_id column, change UC to (user_id, profile_id, task_name).

Revision ID: 012
Revises: 011
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str = "011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("scheduler_state", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("profile_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_index("ix_scheduler_state_profile_id", ["profile_id"])
        batch_op.create_foreign_key(
            "fk_scheduler_state_profile_id",
            "profiles",
            ["profile_id"], ["id"],
            ondelete="CASCADE",
        )
        batch_op.drop_constraint("uq_scheduler_state_user_task", type_="unique")
        batch_op.create_unique_constraint(
            "uq_scheduler_state_user_profile_task",
            ["user_id", "profile_id", "task_name"],
        )


def downgrade() -> None:
    with op.batch_alter_table("scheduler_state", recreate="always") as batch_op:
        batch_op.drop_constraint("uq_scheduler_state_user_profile_task", type_="unique")
        batch_op.create_unique_constraint(
            "uq_scheduler_state_user_task",
            ["user_id", "task_name"],
        )
        batch_op.drop_constraint("fk_scheduler_state_profile_id", type_="foreignkey")
        batch_op.drop_index("ix_scheduler_state_profile_id")
        batch_op.drop_column("profile_id")
