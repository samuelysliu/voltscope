from datetime import UTC, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import AppError
from app.models import Ad, Article, ArticleTag, ArticleTopic, ArticleTranslation, Author, Comment, Tag, Topic
from app.schemas.content import (
    ArticleCreate,
    ArticleOut,
    CommentOut,
    PublicAdOut,
    PublicArticleDetailOut,
    PublicArticleSummary,
    PublicHomeOut,
    PublicTopicPageOut,
    TagOut,
    TopicOut,
)
from app.services.sanitize import sanitize_html


def published_filter(stmt: Select) -> Select:
    now = datetime.now(UTC)
    return stmt.where(
        Article.status == "published",
        Article.deleted_at.is_(None),
        Article.published_at <= now,
        ArticleTranslation.translation_status == "published",
    )


async def serialize_article(article: Article, translation: ArticleTranslation, session: AsyncSession) -> ArticleOut:
    tags_result = await session.execute(
        select(Tag).join(ArticleTag, ArticleTag.tag_id == Tag.id).where(ArticleTag.article_id == article.id)
    )
    tags = [TagOut.model_validate(tag) for tag in tags_result.scalars().all()]
    topics = await list_article_topics(session, article.id)
    return ArticleOut(
        id=article.id,
        status=article.status,
        is_featured=article.is_featured,
        show_ads=article.show_ads,
        hero_image_url=article.hero_image_url,
        thumbnail_url=article.thumbnail_url,
        og_image_url=article.og_image_url,
        views_count=article.views_count,
        likes_count=article.likes_count,
        comments_count=article.comments_count,
        published_at=article.published_at,
        author=article.author,
        tags=tags,
        topics=topics,
        locale=translation.locale,
        title=translation.title,
        slug=translation.slug,
        excerpt=translation.excerpt,
        content_html=translation.content_html,
        content_text=translation.content_text,
        seo_title=translation.seo_title,
        seo_description=translation.seo_description,
        canonical_url=translation.canonical_url,
        updated_at=translation.updated_at,
    )


async def list_article_topics(session: AsyncSession, article_id: str) -> list[TopicOut]:
    result = await session.execute(
        select(Topic)
        .join(ArticleTopic, ArticleTopic.topic_id == Topic.id)
        .where(ArticleTopic.article_id == article_id)
        .order_by(ArticleTopic.is_primary.desc(), Topic.name_en)
    )
    return [TopicOut.model_validate(topic) for topic in result.scalars().all()]


def summarize_article(article: ArticleOut) -> PublicArticleSummary:
    return PublicArticleSummary(
        id=article.id,
        title=article.title,
        slug=article.slug,
        excerpt=article.excerpt,
        locale=article.locale,
        published_at=article.published_at,
        updated_at=article.updated_at,
        hero_image_url=article.hero_image_url,
        thumbnail_url=article.thumbnail_url,
        views_count=article.views_count,
        likes_count=article.likes_count,
        comments_count=article.comments_count,
        topics=article.topics,
    )


async def list_public_articles(
    session: AsyncSession,
    locale: str,
    page: int,
    page_size: int,
    tag: str | None = None,
) -> tuple[list[ArticleOut], int]:
    stmt = (
        select(Article, ArticleTranslation)
        .join(ArticleTranslation)
        .join(Author)
        .options(selectinload(Article.author))
        .where(ArticleTranslation.locale == locale)
        .order_by(Article.published_at.desc())
    )
    stmt = published_filter(stmt)
    if tag:
        stmt = (
            stmt.join(ArticleTopic, ArticleTopic.article_id == Article.id)
            .join(Topic, Topic.id == ArticleTopic.topic_id)
            .where(Topic.slug == tag)
        )
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total = await session.scalar(total_stmt) or 0
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()
    return [await serialize_article(article, translation, session) for article, translation in rows], total


async def get_public_article(session: AsyncSession, locale: str, slug: str) -> ArticleOut:
    row = (
        await session.execute(
            published_filter(
                select(Article, ArticleTranslation)
                .join(ArticleTranslation)
                .options(selectinload(Article.author))
                .where(ArticleTranslation.locale == locale, ArticleTranslation.slug == slug)
            )
        )
    ).first()
    if row is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    article, translation = row
    return await serialize_article(article, translation, session)


async def list_topics(session: AsyncSession) -> list[TopicOut]:
    rows = (await session.execute(select(Topic).order_by(Topic.name_en))).scalars().all()
    return [TopicOut.model_validate(row) for row in rows]


async def list_active_ads(session: AsyncSession, placement: str | tuple[str, ...]) -> list[PublicAdOut]:
    now = datetime.now(UTC)
    placements = (placement,) if isinstance(placement, str) else placement
    rows = (
        await session.execute(
            select(Ad)
            .where(
                Ad.is_active.is_(True),
                or_(Ad.placement.in_(placements), Ad.placement_key.in_(placements)),
                or_(Ad.starts_at.is_(None), Ad.starts_at <= now),
                or_(Ad.ends_at.is_(None), Ad.ends_at >= now),
            )
            .order_by(Ad.weight.desc(), Ad.sort_order)
        )
    ).scalars().all()
    return [
        PublicAdOut(
            id=ad.id,
            name=ad.name or ad.title,
            image_url=ad.image_url,
            target_url=ad.target_url,
            alt_text=ad.alt_text,
            placement=ad.placement or ad.placement_key,
            weight=ad.weight,
        )
        for ad in rows
        if ad.image_url
    ]


async def get_public_home(session: AsyncSession, locale: str) -> PublicHomeOut:
    latest, _ = await list_public_articles(session, locale, 1, 8)
    featured_rows = (
        await session.execute(
            published_filter(
                select(Article, ArticleTranslation)
                .join(ArticleTranslation)
                .options(selectinload(Article.author))
                .where(ArticleTranslation.locale == locale, Article.is_featured.is_(True))
                .order_by(Article.published_at.desc())
                .limit(5)
            )
        )
    ).all()
    featured = [await serialize_article(article, translation, session) for article, translation in featured_rows]
    return PublicHomeOut(
        latest_articles=[summarize_article(article) for article in latest],
        featured_articles=[summarize_article(article) for article in featured],
        topics=await list_topics(session),
        active_home_ads=await list_active_ads(session, "home"),
    )


async def get_public_topic_page(
    session: AsyncSession,
    locale: str,
    slug: str,
    page: int,
    page_size: int,
) -> PublicTopicPageOut:
    topic = await session.scalar(select(Topic).where(Topic.slug == slug))
    if topic is None:
        raise AppError("TOPIC_NOT_FOUND", "Topic not found", 404)
    articles, total = await list_public_articles(session, locale, page, page_size, slug)
    return PublicTopicPageOut(
        topic=TopicOut.model_validate(topic),
        articles=[summarize_article(article) for article in articles],
        total=total,
        page=page,
        page_size=page_size,
    )


async def get_public_article_detail(session: AsyncSession, locale: str, slug: str) -> PublicArticleDetailOut:
    article = await get_public_article(session, locale, slug)
    comments_rows = (
        await session.execute(
            select(Comment)
            .where(Comment.article_id == article.id, Comment.status.in_(["approved", "visible"]))
            .order_by(Comment.created_at.desc())
        )
    ).scalars().all()
    previous_article, next_article = await get_adjacent_articles(session, locale, article)
    return PublicArticleDetailOut(
        article=article,
        translation=article,
        topics=article.topics,
        comments=[
            CommentOut(
                id=comment.id,
                author_name=comment.author_name,
                body=comment.content or comment.body,
                status=comment.status,
                created_at=comment.created_at,
            )
            for comment in comments_rows
        ],
        ads=await list_active_ads(session, ("article_top", "article_middle", "article_bottom", "sidebar")) if article.show_ads else [],
        previous_article=previous_article,
        next_article=next_article,
    )


async def get_adjacent_articles(
    session: AsyncSession,
    locale: str,
    current: ArticleOut,
) -> tuple[PublicArticleSummary | None, PublicArticleSummary | None]:
    if not current.topics or current.published_at is None:
        return None, None
    primary_topic_id = current.topics[0].id

    async def find_one(before: bool) -> PublicArticleSummary | None:
        comparator = Article.published_at < current.published_at if before else Article.published_at > current.published_at
        ordering = Article.published_at.desc() if before else Article.published_at.asc()
        row = (
            await session.execute(
                published_filter(
                    select(Article, ArticleTranslation)
                    .join(ArticleTranslation)
                    .join(ArticleTopic, ArticleTopic.article_id == Article.id)
                    .options(selectinload(Article.author))
                    .where(
                        ArticleTranslation.locale == locale,
                        ArticleTopic.topic_id == primary_topic_id,
                        Article.id != current.id,
                        comparator,
                    )
                    .order_by(ordering)
                    .limit(1)
                )
            )
        ).first()
        if row is None:
            return None
        article, translation = row
        return summarize_article(await serialize_article(article, translation, session))

    return await find_one(True), await find_one(False)


async def create_article(session: AsyncSession, payload: ArticleCreate, user_id: str) -> Article:
    article = Article(
        author_id=payload.author_id,
        status=payload.status,
        is_featured=payload.is_featured,
        created_by=user_id,
        updated_by=user_id,
        published_at=datetime.now(UTC) if payload.status == "published" else None,
        first_published_at=datetime.now(UTC) if payload.status == "published" else None,
    )
    session.add(article)
    await session.flush()
    for item in payload.translations:
        session.add(
            ArticleTranslation(
                article_id=article.id,
                locale=item.locale,
                title=item.title,
                slug=item.slug,
                excerpt=item.excerpt,
                content_json=item.content_json,
                content_html=sanitize_html(item.content_html),
                content_text=item.content_text,
                seo_title=item.seo_title,
                seo_description=item.seo_description,
                og_title=item.og_title,
                og_description=item.og_description,
                translation_status=item.translation_status,
            )
        )
    for tag_id in payload.tag_ids:
        session.add(ArticleTag(article_id=article.id, tag_id=tag_id))
    await session.commit()
    await session.refresh(article)
    return article


async def search_public_articles(session: AsyncSession, locale: str, q: str, page: int, page_size: int) -> tuple[list[ArticleOut], int]:
    pattern = f"%{q}%"
    stmt = (
        select(Article, ArticleTranslation)
        .join(ArticleTranslation)
        .options(selectinload(Article.author))
        .where(ArticleTranslation.locale == locale)
        .where(
            ArticleTranslation.title.ilike(pattern)
            | ArticleTranslation.excerpt.ilike(pattern)
            | ArticleTranslation.content_text.ilike(pattern)
        )
        .order_by(Article.published_at.desc())
    )
    stmt = published_filter(stmt)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).all()
    return [await serialize_article(article, translation, session) for article, translation in rows], total
