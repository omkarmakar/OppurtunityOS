"""Add per-profile digest scheduling fields.

Revision ID: 015
Revises: 014
Create Date: 2026-07-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add digest scheduling columns to profiles table."""
    op.add_column(
        "profiles",
        sa.Column(
            "digest_timezone",
            sa.String(50),
            nullable=False,
            server_default="UTC",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "digest_schedule_hour",
            sa.Integer(),
            nullable=False,
            server_default="8",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "digest_schedule_minute",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "digest_frequency",
            sa.String(20),
            nullable=False,
            server_default="daily",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "digest_weekly_day",
            sa.Integer(),
            nullable=True,
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "instant_alert_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "profiles",
        sa.Column(
            "instant_alert_threshold",
            sa.Integer(),
            nullable=False,
            server_default="80",
        ),
    )
    op.create_index(
        "ix_profiles_digest_timezone",
        "profiles",
        ["digest_timezone"],
    )


def downgrade() -> None:
    """Remove digest scheduling columns from profiles table."""
    op.drop_index("ix_profiles_digest_timezone", table_name="profiles")
    op.drop_column("profiles", "instant_alert_threshold")
    op.drop_column("profiles", "instant_alert_enabled")
    op.drop_column("profiles", "digest_weekly_day")
    op.drop_column("profiles", "digest_frequency")
    op.drop_column("profiles", "digest_schedule_minute")
    op.drop_column("profiles", "digest_schedule_hour")
    op.drop_column("profiles", "digest_timezone")
