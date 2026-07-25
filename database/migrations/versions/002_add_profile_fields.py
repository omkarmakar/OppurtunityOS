"""Add profile management fields to profiles table.

Revision ID: 002
Revises: 001
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("education", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("experience", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("skills", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("preferred_locations", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("salary_expectations", sa.String(200), nullable=True))
    op.add_column("profiles", sa.Column("target_companies", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("keywords", sa.JSON(), nullable=True))
    op.add_column("profiles", sa.Column("resume_path", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("linkedin_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("github_url", sa.String(500), nullable=True))
    op.add_column("profiles", sa.Column("portfolio", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "portfolio")
    op.drop_column("profiles", "github_url")
    op.drop_column("profiles", "linkedin_url")
    op.drop_column("profiles", "resume_path")
    op.drop_column("profiles", "keywords")
    op.drop_column("profiles", "target_companies")
    op.drop_column("profiles", "salary_expectations")
    op.drop_column("profiles", "preferred_locations")
    op.drop_column("profiles", "skills")
    op.drop_column("profiles", "experience")
    op.drop_column("profiles", "education")
