from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="member")
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmailVerificationToken(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "email_verification_tokens"
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class MediaAsset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "media_assets"
    storage_provider: Mapped[str] = mapped_column(String(40), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    alt_zh: Mapped[str | None] = mapped_column(String(255))
    alt_en: Mapped[str | None] = mapped_column(String(255))
    caption_zh: Mapped[str | None] = mapped_column(Text)
    caption_en: Mapped[str | None] = mapped_column(Text)
    credit: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    variants: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)


class Author(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "authors"
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    avatar_media_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("media_assets.id"))
    bio_zh: Mapped[str | None] = mapped_column(Text)
    bio_en: Mapped[str | None] = mapped_column(Text)
    website_url: Mapped[str | None] = mapped_column(String(1000))
    social_links: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    articles: Mapped[list["Article"]] = relationship(back_populates="author")


class Article(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "articles"
    author_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("authors.id"), nullable=False, index=True)
    cover_media_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("media_assets.id"))
    admin_author_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    hero_image_url: Mapped[str | None] = mapped_column(String(1000))
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000))
    og_image_url: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False, default="blog")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_comments_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    show_ads: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    views_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    likes_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    comments_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    primary_source_url: Mapped[str | None] = mapped_column(String(1000))
    primary_source_name: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    updated_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    author: Mapped[Author] = relationship(back_populates="articles")
    translations: Mapped[list["ArticleTranslation"]] = relationship(back_populates="article", cascade="all, delete-orphan")
    tags: Mapped[list["ArticleTag"]] = relationship(back_populates="article", cascade="all, delete-orphan")


class ArticleTranslation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "article_translations"
    __table_args__ = (UniqueConstraint("locale", "slug"), UniqueConstraint("article_id", "locale"))
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False, index=True)
    locale: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(220), nullable=False, index=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    seo_title: Mapped[str | None] = mapped_column(String(255))
    seo_description: Mapped[str | None] = mapped_column(String(320))
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    og_title: Mapped[str | None] = mapped_column(String(255))
    og_description: Mapped[str | None] = mapped_column(String(320))
    translation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    article: Mapped[Article] = relationship(back_populates="translations")


class Tag(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    description_zh: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Topic(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    slug: Mapped[str] = mapped_column(String(180), unique=True, nullable=False, index=True)
    name_zh: Mapped[str] = mapped_column(String(120), nullable=False)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    description_zh: Mapped[str | None] = mapped_column(Text)
    description_en: Mapped[str | None] = mapped_column(Text)


class ArticleTopic(Base):
    __tablename__ = "article_topics"
    __table_args__ = (UniqueConstraint("article_id", "topic_id"),)
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id"), primary_key=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ArticleTag(Base):
    __tablename__ = "article_tags"
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), primary_key=True)
    tag_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("tags.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    article: Mapped[Article] = relationship(back_populates="tags")
    tag: Mapped[Tag] = relationship()


class Comment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "comments"
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    parent_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("comments.id"))
    author_name: Mapped[str] = mapped_column(String(160), nullable=False)
    author_email: Mapped[str] = mapped_column(String(320), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    ip_hash: Mapped[str | None] = mapped_column(String(128))
    user_agent_hash: Mapped[str | None] = mapped_column(String(128))
    moderated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    moderated_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))


class ArticleLike(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "article_likes"
    __table_args__ = (UniqueConstraint("article_id", "visitor_key_hash"), UniqueConstraint("article_id", "user_id"))
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    visitor_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class ArticleViewDaily(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "article_view_daily"
    __table_args__ = (UniqueConstraint("article_id", "view_date"),)
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    view_date: Mapped[date] = mapped_column(Date, nullable=False)
    view_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    unique_view_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)


class ArticleViewDedup(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "article_view_dedup"
    __table_args__ = (UniqueConstraint("article_id", "view_date", "visitor_key_hash"),)
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    view_date: Mapped[date] = mapped_column(Date, nullable=False)
    visitor_key_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Placement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "placements"
    placement_key: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    placement_type: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PlacementArticle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "placement_articles"
    __table_args__ = (UniqueConstraint("placement_id", "article_id"),)
    placement_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("placements.id"), nullable=False)
    article_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AdCampaign(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ad_campaigns"
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    advertiser_name: Mapped[str | None] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Ad(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ads"
    campaign_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("ad_campaigns.id"), nullable=False)
    placement_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    locale: Mapped[str | None] = mapped_column(String(20))
    title: Mapped[str | None] = mapped_column(String(180))
    image_media_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("media_assets.id"), nullable=False)
    target_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    alt_text: Mapped[str] = mapped_column(String(255), nullable=False)
    open_in_new_tab: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    impression_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    click_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    name: Mapped[str | None] = mapped_column(String(180))
    image_url: Mapped[str | None] = mapped_column(String(1000))
    placement: Mapped[str | None] = mapped_column(String(80))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AiSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_sources"
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    base_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    rss_url: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="website")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SourceWhitelist(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "source_whitelist"
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    list_url: Mapped[str | None] = mapped_column(String(1000))
    rss_url: Mapped[str | None] = mapped_column(String(1000))
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_group: Mapped[str] = mapped_column(String(60), nullable=False)
    region: Mapped[str] = mapped_column(String(40), nullable=False)
    default_language: Mapped[str] = mapped_column(String(20), nullable=False, default="mixed")
    trust_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    allowed_topics: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    crawl_method: Mapped[str] = mapped_column(String(40), nullable=False, default="rss")
    quota_role: Mapped[str] = mapped_column(String(40), nullable=False, default="reference_only", index=True)
    allow_auto_publish: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requires_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    crawl_frequency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=360)
    max_candidates_per_run: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    robots_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    health_status: Mapped[str] = mapped_column(String(40), nullable=False, default="healthy", index=True)
    parser_versions: Mapped[list["SourceParserVersion"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    selector_repair_proposals: Mapped[list["SelectorRepairProposal"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    crawler_runs: Mapped[list["CrawlerRun"]] = relationship(back_populates="source")
    content_candidates: Mapped[list["ContentCandidate"]] = relationship(back_populates="source")


class SourceParserVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "source_parser_versions"
    __table_args__ = (UniqueConstraint("source_id", "version"),)
    source_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("source_whitelist.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    parser_type: Mapped[str] = mapped_column(String(40), nullable=False, default="rss")
    selector_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sample_url: Mapped[str | None] = mapped_column(String(1000))
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    validation_status: Mapped[str] = mapped_column(String(40), nullable=False, default="approved", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_by: Mapped[str] = mapped_column(String(40), nullable=False, default="system")
    approved_by: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"))
    validation_result: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[SourceWhitelist] = relationship(back_populates="parser_versions")


class SelectorRepairProposal(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "selector_repair_proposals"
    source_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("source_whitelist.id"), nullable=False, index=True)
    old_parser_version_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("source_parser_versions.id"), nullable=True)
    proposed_selector_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_reasoning_summary: Mapped[str | None] = mapped_column(Text)
    validation_result: Mapped[dict | None] = mapped_column(JSONB)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="proposed", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[SourceWhitelist] = relationship(back_populates="selector_repair_proposals")
    old_parser_version: Mapped[SourceParserVersion | None] = relationship()


class CrawlerRun(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "crawler_runs"
    source_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("source_whitelist.id"), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(40), nullable=False, default="source_test", index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    candidates_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    candidates_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    fallback_used: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    source: Mapped[SourceWhitelist | None] = relationship(back_populates="crawler_runs")
    content_candidates: Mapped[list["ContentCandidate"]] = relationship(back_populates="crawler_run")


class ContentCandidate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "content_candidates"
    __table_args__ = (UniqueConstraint("source_id", "normalized_hash"),)
    crawler_run_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("crawler_runs.id"), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("source_whitelist.id"), nullable=False, index=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False, index=True)
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    source_title: Mapped[str] = mapped_column(Text, nullable=False)
    source_excerpt: Mapped[str | None] = mapped_column(Text)
    source_author: Mapped[str | None] = mapped_column(String(255))
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    normalized_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    raw_text_excerpt: Mapped[str | None] = mapped_column(Text)
    factual_notes: Mapped[dict | None] = mapped_column(JSONB)
    relevance_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    novelty_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    quota_category: Mapped[str] = mapped_column(String(40), nullable=False, default="reference_only", index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500))
    crawler_run: Mapped[CrawlerRun] = relationship(back_populates="content_candidates")
    source: Mapped[SourceWhitelist] = relationship(back_populates="content_candidates")
    generation_jobs: Mapped[list["ArticleGenerationJob"]] = relationship(back_populates="candidate")


class ArticleGenerationJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "article_generation_jobs"
    candidate_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("content_candidates.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="mistral")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_gate_result: Mapped[dict | None] = mapped_column(JSONB)
    generated_article_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("articles.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    candidate: Mapped[ContentCandidate] = relationship(back_populates="generation_jobs")
    generated_article: Mapped[Article | None] = relationship()
    mistral_logs: Mapped[list["MistralGenerationLog"]] = relationship(back_populates="generation_job")


class MistralGenerationLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mistral_generation_logs"
    generation_job_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("article_generation_jobs.id"), nullable=True, index=True)
    purpose: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    input_token_count: Mapped[int | None] = mapped_column(Integer)
    output_token_count: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    generation_job: Mapped[ArticleGenerationJob | None] = relationship(back_populates="mistral_logs")


class DailyContentReport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "daily_content_reports"
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="warning", index=True)
    total_published: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_ready_for_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    taiwan_media_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    international_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_driven_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quota_met: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    quota_detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    failed_sources: Mapped[list | None] = mapped_column(JSONB)
    degraded_sources: Mapped[list | None] = mapped_column(JSONB)
    message: Mapped[str | None] = mapped_column(Text)


class AiIngestJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_ingest_jobs"
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class AiArticleCandidate(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_article_candidates"
    job_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("ai_ingest_jobs.id"), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_name: Mapped[str] = mapped_column(String(180), nullable=False)
    source_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_excerpt: Mapped[str | None] = mapped_column(Text)
    normalized_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    decision: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class SiteSetting(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "site_settings"
    setting_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    value_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    updated_by: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class AuditLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_logs"
    actor_user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
    before_json: Mapped[dict | None] = mapped_column(JSONB)
    after_json: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)


class Redirect(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "redirects"
    locale: Mapped[str] = mapped_column(String(20), nullable=False)
    old_path: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    new_path: Mapped[str] = mapped_column(String(500), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=301)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
