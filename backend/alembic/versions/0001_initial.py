"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_table(
        "media_assets",
        sa.Column("storage_provider", sa.String(40), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_zh", sa.String(255), nullable=True),
        sa.Column("alt_en", sa.String(255), nullable=True),
        sa.Column("caption_zh", sa.Text(), nullable=True),
        sa.Column("caption_en", sa.Text(), nullable=True),
        sa.Column("credit", sa.String(255), nullable=True),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("variants", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_media_assets_storage_key", "media_assets", ["storage_key"])
    op.create_table(
        "authors",
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("avatar_media_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("bio_zh", sa.Text(), nullable=True),
        sa.Column("bio_en", sa.Text(), nullable=True),
        sa.Column("website_url", sa.String(1000), nullable=True),
        sa.Column("social_links", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["avatar_media_id"], ["media_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_authors_slug", "authors", ["slug"])
    op.create_table(
        "tags",
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("name_zh", sa.String(120), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("description_zh", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("ix_tags_slug", "tags", ["slug"])
    op.create_table(
        "articles",
        sa.Column("author_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("cover_media_id", postgresql.UUID(as_uuid=False), nullable=True),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("content_type", sa.String(40), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_comments_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["author_id"], ["authors.id"]),
        sa.ForeignKeyConstraint(["cover_media_id"], ["media_assets.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_articles_author_id", "articles", ["author_id"])
    op.create_index("ix_articles_status", "articles", ["status"])
    op.create_index("ix_articles_is_featured", "articles", ["is_featured"])
    op.create_index("ix_articles_published_at", "articles", ["published_at"])
    op.create_index("ix_articles_deleted_at", "articles", ["deleted_at"])
    op.create_table(
        "article_translations",
        sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("content_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("seo_title", sa.String(255), nullable=True),
        sa.Column("seo_description", sa.String(320), nullable=True),
        sa.Column("og_title", sa.String(255), nullable=True),
        sa.Column("og_description", sa.String(320), nullable=True),
        sa.Column("translation_status", sa.String(40), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("article_id", "locale"),
        sa.UniqueConstraint("locale", "slug"),
    )
    op.create_index("ix_article_translations_article_id", "article_translations", ["article_id"])
    op.create_index("ix_article_translations_locale", "article_translations", ["locale"])
    op.create_index("ix_article_translations_slug", "article_translations", ["slug"])
    op.create_index("ix_article_translations_translation_status", "article_translations", ["translation_status"])
    op.create_table("article_tags", sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("tag_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.ForeignKeyConstraint(["tag_id"], ["tags.id"]), sa.PrimaryKeyConstraint("article_id", "tag_id"))
    op.create_table("comments", sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("parent_id", postgresql.UUID(as_uuid=False), nullable=True), sa.Column("author_name", sa.String(160), nullable=False), sa.Column("author_email", sa.String(320), nullable=False), sa.Column("body", sa.Text(), nullable=False), sa.Column("status", sa.String(40), nullable=False), sa.Column("ip_hash", sa.String(128), nullable=True), sa.Column("user_agent_hash", sa.String(128), nullable=True), sa.Column("moderated_at", sa.DateTime(timezone=True), nullable=True), sa.Column("moderated_by", postgresql.UUID(as_uuid=False), nullable=True), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.ForeignKeyConstraint(["moderated_by"], ["users.id"]), sa.ForeignKeyConstraint(["parent_id"], ["comments.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_comments_article_id", "comments", ["article_id"])
    op.create_index("ix_comments_status", "comments", ["status"])
    op.create_table("article_likes", sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("visitor_key_hash", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("article_id", "visitor_key_hash"))
    op.create_table("article_view_daily", sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("view_date", sa.Date(), nullable=False), sa.Column("view_count", sa.BigInteger(), nullable=False), sa.Column("unique_view_count", sa.BigInteger(), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("article_id", "view_date"))
    op.create_table("article_view_dedup", sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("view_date", sa.Date(), nullable=False), sa.Column("visitor_key_hash", sa.String(128), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("article_id", "view_date", "visitor_key_hash"))
    op.create_table("placements", sa.Column("placement_key", sa.String(120), nullable=False), sa.Column("display_name", sa.String(160), nullable=False), sa.Column("placement_type", sa.String(80), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("placement_key"))
    op.create_table("placement_articles", sa.Column("placement_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("article_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("sort_order", sa.Integer(), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["article_id"], ["articles.id"]), sa.ForeignKeyConstraint(["placement_id"], ["placements.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("placement_id", "article_id"))
    op.create_table("ad_campaigns", sa.Column("name", sa.String(180), nullable=False), sa.Column("advertiser_name", sa.String(180), nullable=True), sa.Column("status", sa.String(40), nullable=False), sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True), sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_table("ads", sa.Column("campaign_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("placement_key", sa.String(120), nullable=False), sa.Column("locale", sa.String(20), nullable=True), sa.Column("title", sa.String(180), nullable=True), sa.Column("image_media_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("target_url", sa.String(1000), nullable=False), sa.Column("alt_text", sa.String(255), nullable=False), sa.Column("open_in_new_tab", sa.Boolean(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("sort_order", sa.Integer(), nullable=False), sa.Column("impression_count", sa.BigInteger(), nullable=False), sa.Column("click_count", sa.BigInteger(), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.ForeignKeyConstraint(["campaign_id"], ["ad_campaigns.id"]), sa.ForeignKeyConstraint(["image_media_id"], ["media_assets.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_ads_placement_key", "ads", ["placement_key"])
    op.create_table("site_settings", sa.Column("setting_key", sa.String(160), nullable=False), sa.Column("value_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False), sa.Column("updated_by", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.ForeignKeyConstraint(["updated_by"], ["users.id"]), sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("setting_key"))
    op.create_table("audit_logs", sa.Column("actor_user_id", postgresql.UUID(as_uuid=False), nullable=False), sa.Column("action", sa.String(120), nullable=False), sa.Column("entity_type", sa.String(120), nullable=False), sa.Column("entity_id", postgresql.UUID(as_uuid=False), nullable=True), sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True), sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"]), sa.PrimaryKeyConstraint("id"))
    op.create_table("redirects", sa.Column("locale", sa.String(20), nullable=False), sa.Column("old_path", sa.String(500), nullable=False), sa.Column("new_path", sa.String(500), nullable=False), sa.Column("status_code", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("id", postgresql.UUID(as_uuid=False), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_redirects_old_path", "redirects", ["old_path"])


def downgrade() -> None:
    for table in [
        "redirects",
        "audit_logs",
        "site_settings",
        "ads",
        "ad_campaigns",
        "placement_articles",
        "placements",
        "article_view_dedup",
        "article_view_daily",
        "article_likes",
        "comments",
        "article_tags",
        "article_translations",
        "articles",
        "tags",
        "authors",
        "media_assets",
        "users",
    ]:
        op.drop_table(table)

