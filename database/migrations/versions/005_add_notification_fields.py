"""Add channel, delivery, and digest fields to notifications.

Revision ID: 005
Revises: 004
Create Date: 2026-07-25
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: str = "004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("notifications", sa.Column("channel", sa.String(20), nullable=False, server_default="in_app"))
    op.add_column("notifications", sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("notifications", sa.Column("metadata_json", sa.Text(), nullable=True))
    op.add_column("notifications", sa.Column("email_to", sa.String(255), nullable=True))
    op.add_column("notifications", sa.Column("digest_id", sa.Uuid(), nullable=True, index=True))


def downgrade() -> None:
    op.drop_column("notifications", "digest_id")
    op.drop_column("notifications", "email_to")
    op.drop_column("notifications", "metadata_json")
    op.drop_column("notifications", "delivered_at")
    op.drop_column("notifications", "channel")
