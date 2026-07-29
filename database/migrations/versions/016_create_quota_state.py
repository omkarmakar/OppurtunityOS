"""Create quota_state table.

Revision ID: 016
Revises: 015
Create Date: 2026-07-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str = "015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "quota_state",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=False),
        sa.Column("remaining", sa.Integer(), nullable=True),
        sa.Column("quota_limit", sa.Integer(), nullable=True),
        sa.Column("reset_at", sa.Float(), nullable=True),
        sa.Column(
            "last_updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_name", name="uq_quota_state_provider"),
    )
    op.create_index(
        op.f("ix_quota_state_provider_name"), "quota_state", ["provider_name"]
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_quota_state_provider_name"), table_name="quota_state")
    op.drop_table("quota_state")
