from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    display_name: str
    bio_zh: str | None = None
    bio_en: str | None = None


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name_zh: str
    name_en: str


class TopicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    slug: str
    name_zh: str
    name_en: str
    description_zh: str | None = None
    description_en: str | None = None


class ArticleTranslationIn(BaseModel):
    locale: str
    title: str = Field(min_length=1, max_length=255)
    slug: str = Field(min_length=1, max_length=220, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    excerpt: str = Field(min_length=1)
    content_json: dict[str, Any] = Field(default_factory=dict)
    content_html: str = Field(min_length=1)
    content_text: str = Field(min_length=1)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=320)
    og_title: str | None = Field(default=None, max_length=255)
    og_description: str | None = Field(default=None, max_length=320)
    translation_status: str = "draft"


class ArticleOut(BaseModel):
    id: str
    status: str
    is_featured: bool
    show_ads: bool = True
    hero_image_url: str | None = None
    thumbnail_url: str | None = None
    og_image_url: str | None = None
    views_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    published_at: datetime | None
    author: AuthorOut
    tags: list[TagOut] = []
    topics: list[TopicOut] = []
    locale: str
    title: str
    slug: str
    excerpt: str
    content_html: str
    content_text: str
    seo_title: str | None = None
    seo_description: str | None = None
    canonical_url: str | None = None
    updated_at: datetime


class PublicArticleSummary(BaseModel):
    id: str
    title: str
    slug: str
    excerpt: str
    locale: str
    published_at: datetime | None
    updated_at: datetime
    hero_image_url: str | None = None
    thumbnail_url: str | None = None
    views_count: int = 0
    likes_count: int = 0
    comments_count: int = 0
    topics: list[TopicOut] = []


class PublicAdOut(BaseModel):
    id: str
    name: str | None = None
    image_url: str | None = None
    target_url: str
    alt_text: str
    placement: str
    weight: int = 0


class PublicHomeOut(BaseModel):
    latest_articles: list[PublicArticleSummary]
    featured_articles: list[PublicArticleSummary]
    topics: list[TopicOut]
    active_home_ads: list[PublicAdOut]


class PublicTopicPageOut(BaseModel):
    topic: TopicOut
    articles: list[PublicArticleSummary]
    total: int
    page: int
    page_size: int


class PublicArticleDetailOut(BaseModel):
    article: ArticleOut
    translation: ArticleOut
    topics: list[TopicOut]
    comments: list[CommentOut]
    ads: list[PublicAdOut]
    previous_article: PublicArticleSummary | None = None
    next_article: PublicArticleSummary | None = None


class PublicArticleListOut(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class PublicArticleSearchOut(BaseModel):
    items: list[ArticleOut]
    total: int
    page: int
    page_size: int


class ViewRecordOut(BaseModel):
    ok: bool
    unique: bool


class ActionOkOut(BaseModel):
    ok: bool


class MemberLikeOut(BaseModel):
    liked: bool
    count: int


class ArticleCreate(BaseModel):
    author_id: str
    status: str = "draft"
    is_featured: bool = False
    translations: list[ArticleTranslationIn]
    tag_ids: list[str] = Field(default_factory=list)


class CommentCreate(BaseModel):
    author_name: str = Field(min_length=1, max_length=160)
    author_email: str = Field(min_length=3, max_length=320)
    body: str = Field(min_length=1, max_length=4000)
    website: str | None = None


class MemberCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class CommentOut(BaseModel):
    id: str
    author_name: str
    body: str
    status: str
    created_at: datetime


class AdOut(BaseModel):
    id: str
    placement_key: str
    title: str | None
    image_media_id: str
    target_url: HttpUrl
    alt_text: str
    open_in_new_tab: bool
