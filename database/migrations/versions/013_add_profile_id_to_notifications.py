"""Add nullable profile_id column to notifications table.

Revision ID: 013
Revises: 012
Create Date: 2026-07-27
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str = "012"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("profile_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_index("ix_notifications_profile_id", ["profile_id"])
        batch_op.create_foreign_key(
            "fk_notifications_profile_id",
            "profiles",
            ["profile_id"], ["id"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_notifications_profile_id", type_="foreignkey")
        batch_op.drop_index("ix_notifications_profile_id")
        batch_op.drop_column("profile_id")
