"""Add AI scoring columns to opportunities table.

Revision ID: 004
Revises: 003
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: str = "003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("opportunities", sa.Column("relevance_score", sa.Float(), nullable=True))
    op.add_column("opportunities", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("opportunities", sa.Column("pros", sa.JSON(), nullable=True))
    op.add_column("opportunities", sa.Column("cons", sa.JSON(), nullable=True))
    op.add_column("opportunities", sa.Column("required_skills", sa.JSON(), nullable=True))
    op.add_column("opportunities", sa.Column("missing_skills", sa.JSON(), nullable=True))
    op.add_column("opportunities", sa.Column("application_deadline", sa.String(100), nullable=True))
    op.add_column("opportunities", sa.Column("ranking_explanation", sa.Text(), nullable=True))
    op.add_column("opportunities", sa.Column("ai_scored_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("opportunities", "ai_scored_at")
    op.drop_column("opportunities", "ranking_explanation")
    op.drop_column("opportunities", "application_deadline")
    op.drop_column("opportunities", "missing_skills")
    op.drop_column("opportunities", "required_skills")
    op.drop_column("opportunities", "cons")
    op.drop_column("opportunities", "pros")
    op.drop_column("opportunities", "summary")
    op.drop_column("opportunities", "relevance_score")
