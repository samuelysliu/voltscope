"""phase 7 crawler runs

Revision ID: 0006_phase7_crawler_runs
Revises: 0005_phase7_source_whitelist
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_phase7_crawler_runs"
down_revision = "0005_phase7_source_whitelist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "crawler_runs",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("job_type", sa.String(length=40), nullable=False, server_default="source_test"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("candidates_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("candidates_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("fallback_used", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["source_whitelist.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crawler_runs_job_type", "crawler_runs", ["job_type"])
    op.create_index("ix_crawler_runs_source_id", "crawler_runs", ["source_id"])
    op.create_index("ix_crawler_runs_status", "crawler_runs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_crawler_runs_status", table_name="crawler_runs")
    op.drop_index("ix_crawler_runs_source_id", table_name="crawler_runs")
    op.drop_index("ix_crawler_runs_job_type", table_name="crawler_runs")
    op.drop_table("crawler_runs")
