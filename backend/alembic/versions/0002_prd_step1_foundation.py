"""prd step 1 foundation

Revision ID: 0002_prd_step1_foundation
Revises: 0001_initial
Create Date: 2026-07-09
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_prd_step1_foundation"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.create_table(
        "email_verification_tokens",
        sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_verification_tokens_user_id", "email_verification_tokens", ["user_id"])
    op.create_index("ix_email_verification_tokens_token_hash", "email_verification_tokens", ["token_hash"])

    op.add_column("articles", sa.Column("admin_author_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("articles", sa.Column("hero_image_url", sa.String(1000), nullable=True))
    op.add_column("articles", sa.Column("thumbnail_url", sa.String(1000), nullable=True))
    op.add_column("articles", sa.Column("og_image_url", sa.String(1000), nullable=True))
    op.add_column("articles", sa.Column("show_ads", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("articles", sa.Column("views_count", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("articles", sa.Column("likes_count", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("articles", sa.Column("comments_count", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("articles", sa.Column("source_type", sa.String(40), nullable=False, server_default="manual"))
    op.add_column("articles", sa.Column("primary_source_url", sa.String(1000), nullable=True))
    op.add_column("articles", sa.Column("primary_source_name", sa.String(255), nullable=True))
    op.create_foreign_key("fk_articles_admin_author_id_users", "articles", "users", ["admin_author_id"], ["id"])

    op.add_column("article_translations", sa.Column("canonical_url", sa.String(1000), nullable=True))

    op.create_table(
        "topics",
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("name_zh", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_topics_slug", "topics", ["slug"])

    op.create_table(
        "article_topics",
        sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.ForeignKeyConstraint(["topic_id"], ["topics.id"]),
        sa.PrimaryKeyConstraint("article_id", "topic_id"),
        sa.UniqueConstraint("article_id", "topic_id"),
    )

    op.add_column("comments", sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.add_column("comments", sa.Column("content", sa.Text(), nullable=True))
    op.create_foreign_key("fk_comments_user_id_users", "comments", "users", ["user_id"], ["id"])

    op.add_column("article_likes", sa.Column("user_id", postgresql.UUID(as_uuid=False), nullable=True))
    op.create_foreign_key("fk_article_likes_user_id_users", "article_likes", "users", ["user_id"], ["id"])

    op.add_column("ads", sa.Column("name", sa.String(180), nullable=True))
    op.add_column("ads", sa.Column("image_url", sa.String(1000), nullable=True))
    op.add_column("ads", sa.Column("placement", sa.String(80), nullable=True))
    op.add_column("ads", sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ads", sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("ads", sa.Column("weight", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "ai_sources",
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("base_url", sa.String(1000), nullable=False),
        sa.Column("rss_url", sa.String(1000), nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ai_ingest_jobs",
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "ai_article_candidates",
        sa.Column("job_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("source_title", sa.String(500), nullable=False),
        sa.Column("source_name", sa.String(180), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_excerpt", sa.Text(), nullable=True),
        sa.Column("normalized_hash", sa.String(128), nullable=False),
        sa.Column("decision", sa.String(40), nullable=False),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["ai_ingest_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_article_candidates_normalized_hash", "ai_article_candidates", ["normalized_hash"])


def downgrade() -> None:
    op.drop_index("ix_ai_article_candidates_normalized_hash", table_name="ai_article_candidates")
    op.drop_table("ai_article_candidates")
    op.drop_table("ai_ingest_jobs")
    op.drop_table("ai_sources")

    for column in ["weight", "ends_at", "starts_at", "placement", "image_url", "name"]:
        op.drop_column("ads", column)

    op.drop_constraint("fk_article_likes_user_id_users", "article_likes", type_="foreignkey")
    op.drop_column("article_likes", "user_id")

    op.drop_constraint("fk_comments_user_id_users", "comments", type_="foreignkey")
    op.drop_column("comments", "content")
    op.drop_column("comments", "user_id")

    op.drop_table("article_topics")
    op.drop_index("ix_topics_slug", table_name="topics")
    op.drop_table("topics")

    op.drop_column("article_translations", "canonical_url")

    op.drop_constraint("fk_articles_admin_author_id_users", "articles", type_="foreignkey")
    for column in [
        "primary_source_name",
        "primary_source_url",
        "source_type",
        "comments_count",
        "likes_count",
        "views_count",
        "show_ads",
        "og_image_url",
        "thumbnail_url",
        "hero_image_url",
        "admin_author_id",
    ]:
        op.drop_column("articles", column)

    op.drop_index("ix_email_verification_tokens_token_hash", table_name="email_verification_tokens")
    op.drop_index("ix_email_verification_tokens_user_id", table_name="email_verification_tokens")
    op.drop_table("email_verification_tokens")
    op.drop_column("users", "email_verified")
