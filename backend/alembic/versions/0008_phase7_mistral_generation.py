"""phase 7 mistral generation

Revision ID: 0008_phase7_mistral_generation
Revises: 0007_phase7_content_candidates
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_phase7_mistral_generation"
down_revision = "0007_phase7_content_candidates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article_generation_jobs",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("provider", sa.String(length=40), nullable=False, server_default="mistral"),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quality_gate_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("generated_article_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["content_candidates.id"]),
        sa.ForeignKeyConstraint(["generated_article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_article_generation_jobs_candidate_id", "article_generation_jobs", ["candidate_id"])
    op.create_index("ix_article_generation_jobs_status", "article_generation_jobs", ["status"])

    op.create_table(
        "mistral_generation_logs",
        sa.Column("generation_job_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("purpose", sa.String(length=60), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("input_token_count", sa.Integer(), nullable=True),
        sa.Column("output_token_count", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["generation_job_id"], ["article_generation_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mistral_generation_logs_generation_job_id", "mistral_generation_logs", ["generation_job_id"])
    op.create_index("ix_mistral_generation_logs_purpose", "mistral_generation_logs", ["purpose"])
    op.create_index("ix_mistral_generation_logs_status", "mistral_generation_logs", ["status"])


def downgrade() -> None:
    op.drop_index("ix_mistral_generation_logs_status", table_name="mistral_generation_logs")
    op.drop_index("ix_mistral_generation_logs_purpose", table_name="mistral_generation_logs")
    op.drop_index("ix_mistral_generation_logs_generation_job_id", table_name="mistral_generation_logs")
    op.drop_table("mistral_generation_logs")
    op.drop_index("ix_article_generation_jobs_status", table_name="article_generation_jobs")
    op.drop_index("ix_article_generation_jobs_candidate_id", table_name="article_generation_jobs")
    op.drop_table("article_generation_jobs")
