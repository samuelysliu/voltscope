"""phase 7 selector repairs

Revision ID: 0010_phase7_selector_repairs
Revises: 0009_phase7_daily_reports
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0010_phase7_selector_repairs"
down_revision = "0009_phase7_daily_reports"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "selector_repair_proposals",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("old_parser_version_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("proposed_selector_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("agent_reasoning_summary", sa.Text(), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["old_parser_version_id"], ["source_parser_versions.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_whitelist.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_selector_repair_proposals_source_id", "selector_repair_proposals", ["source_id"])
    op.create_index("ix_selector_repair_proposals_status", "selector_repair_proposals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_selector_repair_proposals_status", table_name="selector_repair_proposals")
    op.drop_index("ix_selector_repair_proposals_source_id", table_name="selector_repair_proposals")
    op.drop_table("selector_repair_proposals")
