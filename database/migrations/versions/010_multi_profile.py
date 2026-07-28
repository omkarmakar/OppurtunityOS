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
    # 1. Drop the UNIQUE constraint on user_id.
    #    The original constraint in migration 001 was created as an unnamed
    #    `sa.UniqueConstraint("user_id")`, so SQLite has no stored name for
    #    it. Alembic batch mode cannot drop it by a guessed name; instead,
    #    we provide a naming_convention so Alembic assigns a predictable
    #    name during reflection, making drop_constraint match correctly.
    with op.batch_alter_table(
        "profiles",
        recreate="always",
        naming_convention={
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        },
    ) as batch_op:
        batch_op.drop_constraint("uq_profiles_user_id", type_="unique")
        batch_op.create_index("ix_profiles_user_id", ["user_id"])
        batch_op.add_column(
            sa.Column("name", sa.String(100), nullable=False, server_default="Profile 1"),
        )

    # ── opportunities table changes ────────────────────────────────────
    # Add nullable profile_id column for backward compatibility.
    # Must use batch mode on SQLite for FK and index operations.
    with op.batch_alter_table("opportunities", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("profile_id", sa.Uuid(), nullable=True),
        )
        batch_op.create_foreign_key(
            "fk_opportunities_profile_id",
            "profiles",
            ["profile_id"], ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_opportunities_profile_id",
            ["profile_id"],
        )


def downgrade() -> None:
    # ── opportunities table ────────────────────────────────────────────
    with op.batch_alter_table("opportunities", recreate="always") as batch_op:
        batch_op.drop_index("ix_opportunities_profile_id")
        batch_op.drop_constraint("fk_opportunities_profile_id", type_="foreignkey")
        batch_op.drop_column("profile_id")

    # ── profiles table ─────────────────────────────────────────────────
    with op.batch_alter_table("profiles", recreate="always") as batch_op:
        batch_op.drop_column("name")
        batch_op.drop_index("ix_profiles_user_id")
        batch_op.create_unique_constraint("uq_profiles_user_id", ["user_id"])