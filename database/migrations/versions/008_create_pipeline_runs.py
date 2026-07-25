"""Create pipeline_runs table.

Revision ID: 008
Revises: 007
Create Date: 2026-07-25
"""

from __future__ import annotations

from typing import ClassVar

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: str = "007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("queries_generated", sa.JSON(), nullable=True),
        sa.Column("search_results_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opportunities_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opportunities_skipped_duplicate", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("opportunities_scored", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("step_results", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_pipeline_runs_user_id"), "pipeline_runs", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_pipeline_runs_user_id"), table_name="pipeline_runs")
    op.drop_table("pipeline_runs")
