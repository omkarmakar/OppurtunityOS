"""Add last_seen_at and partial unique index on (user_id, url) to opportunities.

Revision ID: 006
Revises: 005
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: str = "005"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # 1. Add last_seen_at column
    op.add_column("opportunities", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))

    # 2. Remove duplicate opportunities (keep the newest row per user_id + url)
    #    so the partial unique index can be created without errors.
    op.execute(
        """
        DELETE FROM opportunities
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY user_id, url
                           ORDER BY created_at DESC
                       ) AS rn
                FROM opportunities
                WHERE url IS NOT NULL AND url != ''
            ) dup
            WHERE dup.rn > 1
        )
        """
    )

    # 3. Create a partial unique index — only enforced when url is non-empty.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ix_opportunities_user_url
        ON opportunities (user_id, url)
        WHERE url IS NOT NULL AND url != ''
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_opportunities_user_url")
    op.drop_column("opportunities", "last_seen_at")
