"""phase 7 source whitelist

Revision ID: 0005_phase7_source_whitelist
Revises: 0004_phase4_admin_cms
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0005_phase7_source_whitelist"
down_revision = "0004_phase4_admin_cms"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "source_whitelist",
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("homepage_url", sa.String(length=1000), nullable=False),
        sa.Column("list_url", sa.String(length=1000), nullable=True),
        sa.Column("rss_url", sa.String(length=1000), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_group", sa.String(length=60), nullable=False),
        sa.Column("region", sa.String(length=40), nullable=False),
        sa.Column("default_language", sa.String(length=20), nullable=False, server_default="mixed"),
        sa.Column("trust_level", sa.String(length=20), nullable=False, server_default="medium"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allowed_topics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("crawl_method", sa.String(length=40), nullable=False, server_default="rss"),
        sa.Column("quota_role", sa.String(length=40), nullable=False, server_default="reference_only"),
        sa.Column("allow_auto_publish", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("crawl_frequency_minutes", sa.Integer(), nullable=False, server_default="360"),
        sa.Column("max_candidates_per_run", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("robots_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("health_status", sa.String(length=40), nullable=False, server_default="healthy"),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_whitelist_domain", "source_whitelist", ["domain"])
    op.create_index("ix_source_whitelist_enabled", "source_whitelist", ["enabled"])
    op.create_index("ix_source_whitelist_health_status", "source_whitelist", ["health_status"])
    op.create_index("ix_source_whitelist_quota_role", "source_whitelist", ["quota_role"])

    op.create_table(
        "source_parser_versions",
        sa.Column("source_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parser_type", sa.String(length=40), nullable=False, server_default="rss"),
        sa.Column("selector_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sample_url", sa.String(length=1000), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("validation_status", sa.String(length=40), nullable=False, server_default="approved"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", sa.String(length=40), nullable=False, server_default="system"),
        sa.Column("approved_by", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["source_whitelist.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version"),
    )
    op.create_index("ix_source_parser_versions_is_active", "source_parser_versions", ["is_active"])
    op.create_index("ix_source_parser_versions_source_id", "source_parser_versions", ["source_id"])
    op.create_index("ix_source_parser_versions_validation_status", "source_parser_versions", ["validation_status"])


def downgrade() -> None:
    op.drop_index("ix_source_parser_versions_validation_status", table_name="source_parser_versions")
    op.drop_index("ix_source_parser_versions_source_id", table_name="source_parser_versions")
    op.drop_index("ix_source_parser_versions_is_active", table_name="source_parser_versions")
    op.drop_table("source_parser_versions")
    op.drop_index("ix_source_whitelist_quota_role", table_name="source_whitelist")
    op.drop_index("ix_source_whitelist_health_status", table_name="source_whitelist")
    op.drop_index("ix_source_whitelist_enabled", table_name="source_whitelist")
    op.drop_index("ix_source_whitelist_domain", table_name="source_whitelist")
    op.drop_table("source_whitelist")
