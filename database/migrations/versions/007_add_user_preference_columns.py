"""Add pipeline preference columns to application_settings.

Revision ID: 007
Revises: 006
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "007"
down_revision: str = "006"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("application_settings", sa.Column("default_search_provider", sa.String(50), nullable=False, server_default="dummy"))
    op.add_column("application_settings", sa.Column("default_max_queries", sa.Integer(), nullable=False, server_default="5"))
    op.add_column("application_settings", sa.Column("default_max_results", sa.Integer(), nullable=False, server_default="10"))


def downgrade() -> None:
    op.drop_column("application_settings", "default_max_results")
    op.drop_column("application_settings", "default_max_queries")
    op.drop_column("application_settings", "default_search_provider")
