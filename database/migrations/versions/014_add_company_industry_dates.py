"""Add company, industry, and date fields to opportunities table.

Adds structured fields for company name, industry classification, and parsing
of actual posted and deadline dates from job description content. Maintains
backward compatibility by keeping the string application_deadline column
and introducing deadline_at as the new authoritative datetime field, with
application_deadline_raw as fallback for unparseable dates.

Revision ID: 014
Revises: 013
Create Date: 2026-07-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str = "013"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("opportunities", recreate="always") as batch_op:
        # Add new structured fields
        batch_op.add_column(
            sa.Column("company", sa.String(500), nullable=True),
        )
        batch_op.add_column(
            sa.Column("industry", sa.String(200), nullable=True),
        )
        batch_op.add_column(
            sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch_op.add_column(
            sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True),
        )
        # Preserve existing application_deadline data as raw string
        batch_op.add_column(
            sa.Column("application_deadline_raw", sa.String(100), nullable=True),
        )
        
        # Create indexes for new columns
        batch_op.create_index("ix_opportunities_company", ["company"])
        batch_op.create_index("ix_opportunities_industry", ["industry"])
        batch_op.create_index("ix_opportunities_deadline_at", ["deadline_at"])


def downgrade() -> None:
    with op.batch_alter_table("opportunities", recreate="always") as batch_op:
        batch_op.drop_index("ix_opportunities_deadline_at")
        batch_op.drop_index("ix_opportunities_industry")
        batch_op.drop_index("ix_opportunities_company")
        batch_op.drop_column("application_deadline_raw")
        batch_op.drop_column("deadline_at")
        batch_op.drop_column("posted_at")
        batch_op.drop_column("industry")
        batch_op.drop_column("company")
