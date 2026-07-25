"""Add projects JSON column to profiles table.

Revision ID: 003
Revises: 002
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("projects", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "projects")
