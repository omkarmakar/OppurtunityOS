"""Multi-profile support — drop unique on user_id, add name field and profile_id.

Revision ID: 010
Revises: 009
Create Date: 2026-07-26
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: str = "009"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ── profiles table changes ─────────────────────────────────────────
    # 1. Drop the UNIQUE constraint on user_id (Alembic needs the exact
    #    constraint name, which varies per DB; drop by name if known).
    #    SQLite doesn't support DROP CONSTRAINT, so we handle it via batch.
    with op.batch_alter_table("profiles") as batch_op:
        # Drop the unique constraint on user_id
        batch_op.drop_constraint("uq_profiles_user_id", type_="unique")
        # Add a non-unique index on user_id
        batch_op.create_index("ix_profiles_user_id", ["user_id"])
        # Add the name column
        batch_op.add_column(
            sa.Column("name", sa.String(100), nullable=False, server_default="Profile 1"),
        )

    # ── opportunities table changes ────────────────────────────────────
    # Add nullable profile_id column for backward compatibility.
    op.add_column(
        "opportunities",
        sa.Column("profile_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_opportunities_profile_id",
        "opportunities", "profiles",
        ["profile_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_opportunities_profile_id",
        "opportunities",
        ["profile_id"],
    )


def downgrade() -> None:
    # ── opportunities table ────────────────────────────────────────────
    op.drop_index("ix_opportunities_profile_id", table_name="opportunities")
    op.drop_constraint("fk_opportunities_profile_id", "opportunities", type_="foreignkey")
    op.drop_column("opportunities", "profile_id")

    # ── profiles table ─────────────────────────────────────────────────
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_column("name")
        batch_op.drop_index("ix_profiles_user_id")
        batch_op.create_unique_constraint("uq_profiles_user_id", ["user_id"])