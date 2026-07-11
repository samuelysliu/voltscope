"""phase 7 content candidates

Revision ID: 0007_phase7_content_candidates
Revises: 0006_phase7_crawler_runs
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_phase7_content_candidates"
down_revision = "0006_phase7_crawler_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "content_candidates",
        sa.Column("crawler_run_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=True),
        sa.Column("source_title", sa.Text(), nullable=False),
        sa.Column("source_excerpt", sa.Text(), nullable=True),
        sa.Column("source_author", sa.String(length=255), nullable=True),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_hash", sa.String(length=128), nullable=False),
        sa.Column("raw_text_excerpt", sa.Text(), nullable=True),
        sa.Column("factual_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("relevance_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("novelty_score", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("quota_category", sa.String(length=40), nullable=False, server_default="reference_only"),
        sa.Column("decision", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("rejection_reason", sa.String(length=500), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["crawler_run_id"], ["crawler_runs.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_whitelist.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "normalized_hash"),
    )
    op.create_index("ix_content_candidates_crawler_run_id", "content_candidates", ["crawler_run_id"])
    op.create_index("ix_content_candidates_decision", "content_candidates", ["decision"])
    op.create_index("ix_content_candidates_normalized_hash", "content_candidates", ["normalized_hash"])
    op.create_index("ix_content_candidates_quota_category", "content_candidates", ["quota_category"])
    op.create_index("ix_content_candidates_source_id", "content_candidates", ["source_id"])
    op.create_index("ix_content_candidates_source_url", "content_candidates", ["source_url"])


def downgrade() -> None:
    op.drop_index("ix_content_candidates_source_url", table_name="content_candidates")
    op.drop_index("ix_content_candidates_source_id", table_name="content_candidates")
    op.drop_index("ix_content_candidates_quota_category", table_name="content_candidates")
    op.drop_index("ix_content_candidates_normalized_hash", table_name="content_candidates")
    op.drop_index("ix_content_candidates_decision", table_name="content_candidates")
    op.drop_index("ix_content_candidates_crawler_run_id", table_name="content_candidates")
    op.drop_table("content_candidates")
