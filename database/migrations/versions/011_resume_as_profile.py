"""Resume-as-profile columns — raw_extracted_text, resume_filename, resume_uploaded_at, remote_preference.

Revision ID: 011
Revises: 010
Create Date: 2026-07-27
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str = "010"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    with op.batch_alter_table("profiles", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("raw_extracted_text", sa.Text(), nullable=True),
        )
        batch_op.add_column(
            sa.Column("resume_filename", sa.String(255), nullable=True),
        )
        batch_op.add_column(
            sa.Column("resume_uploaded_at", sa.DateTime(timezone=True), nullable=True),
        )
        batch_op.add_column(
            sa.Column("remote_preference", sa.String(50), nullable=True),
        )


def downgrade() -> None:
    with op.batch_alter_table("profiles", recreate="always") as batch_op:
        batch_op.drop_column("remote_preference")
        batch_op.drop_column("resume_uploaded_at")
        batch_op.drop_column("resume_filename")
        batch_op.drop_column("raw_extracted_text")
