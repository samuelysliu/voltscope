"""phase 7 daily content reports

Revision ID: 0009_phase7_daily_reports
Revises: 0008_phase7_mistral_generation
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_phase7_daily_reports"
down_revision = "0008_phase7_mistral_generation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_content_reports",
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="warning"),
        sa.Column("total_published", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_ready_for_review", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("taiwan_media_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("international_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("event_driven_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quota_met", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("quota_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("failed_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("degraded_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("report_date"),
    )
    op.create_index("ix_daily_content_reports_quota_met", "daily_content_reports", ["quota_met"])
    op.create_index("ix_daily_content_reports_report_date", "daily_content_reports", ["report_date"])
    op.create_index("ix_daily_content_reports_status", "daily_content_reports", ["status"])


def downgrade() -> None:
    op.drop_index("ix_daily_content_reports_status", table_name="daily_content_reports")
    op.drop_index("ix_daily_content_reports_report_date", table_name="daily_content_reports")
    op.drop_index("ix_daily_content_reports_quota_met", table_name="daily_content_reports")
    op.drop_table("daily_content_reports")
