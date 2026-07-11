import hashlib
from datetime import UTC, date, datetime
from xml.sax.saxutils import escape

from fastapi import APIRouter, Cookie, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.api.v1.deps import SessionDep
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import Article, ArticleTranslation, ArticleViewDaily, ArticleViewDedup, Author, Comment, Tag, Topic
from app.schemas.content import (
    ArticleOut,
    ActionOkOut,
    AuthorOut,
    CommentCreate,
    CommentOut,
    PublicArticleDetailOut,
    PublicArticleListOut,
    PublicArticleSearchOut,
    PublicHomeOut,
    PublicTopicPageOut,
    TagOut,
    TopicOut,
    ViewRecordOut,
)
from app.services.content import (
    get_public_article,
    get_public_article_detail,
    get_public_home,
    get_public_topic_page,
    list_public_articles,
    list_topics,
    published_filter,
    search_public_articles,
)

router = APIRouter(prefix="/public", tags=["public"])


def hash_visitor(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@router.get("/tags", response_model=list[TagOut])
async def tags(session: SessionDep) -> list[TagOut]:
    rows = (await session.execute(select(Tag).where(Tag.is_active.is_(True)).order_by(Tag.sort_order, Tag.name_en))).scalars().all()
    return [TagOut.model_validate(row) for row in rows]


@router.get("/topics", response_model=list[TopicOut])
async def topics(session: SessionDep) -> list[TopicOut]:
    return await list_topics(session)


@router.get("/home", response_model=PublicHomeOut)
async def home(session: SessionDep, locale: str = Query("zh-TW")) -> PublicHomeOut:
    return await get_public_home(session, locale)


@router.get("/sitemap.xml", response_class=Response)
async def public_sitemap(session: SessionDep) -> Response:
    settings = get_settings()
    host = str(settings.frontend_url).rstrip("/")
    entries: list[str] = []
    topics_rows = (await session.execute(select(Topic).order_by(Topic.slug))).scalars().all()
    for locale, db_locale in [("zh", "zh-TW"), ("en", "en")]:
        entries.append(f"<url><loc>{escape(f'{host}/{locale}')}</loc></url>")
        entries.append(f"<url><loc>{escape(f'{host}/{locale}/articles')}</loc></url>")
        for topic in topics_rows:
            entries.append(f"<url><loc>{escape(f'{host}/{locale}/topics/{topic.slug}')}</loc></url>")
        rows = (
            await session.execute(
                published_filter(
                    select(Article, ArticleTranslation)
                    .join(ArticleTranslation)
                    .where(ArticleTranslation.locale == db_locale)
                    .order_by(Article.updated_at.desc())
                )
            )
        ).all()
        for article, translation in rows:
            updated = (translation.updated_at or article.updated_at).date().isoformat()
            entries.append(
                f"<url><loc>{escape(f'{host}/{locale}/articles/{translation.slug}')}</loc><lastmod>{updated}</lastmod></url>"
            )
    xml = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(entries) + "</urlset>"
    return Response(content=xml, media_type="application/xml")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def public_robots() -> PlainTextResponse:
    settings = get_settings()
    host = str(settings.frontend_url).rstrip("/")
    body = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            "Disallow: /api/admin",
            "Disallow: /api/v1/admin",
            f"Sitemap: {host}/sitemap.xml",
            "",
        ]
    )
    return PlainTextResponse(body)


@router.get("/authors", response_model=list[AuthorOut])
async def authors(session: SessionDep) -> list[AuthorOut]:
    rows = (await session.execute(select(Author).where(Author.is_active.is_(True)).order_by(Author.display_name))).scalars().all()
    return [AuthorOut.model_validate(row) for row in rows]


@router.get("/articles", response_model=PublicArticleListOut)
async def articles(
    session: SessionDep,
    locale: str = Query("zh-TW"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    tag: str | None = None,
) -> PublicArticleListOut:
    items, total = await list_public_articles(session, locale, page, page_size, tag)
    return PublicArticleListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/topics/{locale}/{slug}", response_model=PublicTopicPageOut)
async def topic_detail(
    locale: str,
    slug: str,
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
) -> PublicTopicPageOut:
    return await get_public_topic_page(session, locale, slug, page, page_size)


@router.get("/articles/{locale}/{slug}", response_model=PublicArticleDetailOut)
async def article_detail_page(locale: str, slug: str, session: SessionDep) -> PublicArticleDetailOut:
    return await get_public_article_detail(session, locale, slug)


@router.get("/articles/{slug}", response_model=ArticleOut)
async def article_detail(slug: str, session: SessionDep, locale: str = Query("zh-TW")) -> ArticleOut:
    return await get_public_article(session, locale, slug)


@router.get("/search", response_model=PublicArticleSearchOut)
async def search(
    session: SessionDep,
    q: str = Query(min_length=1),
    locale: str = Query("zh-TW"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> PublicArticleSearchOut:
    items, total = await search_public_articles(session, locale, q, page, page_size)
    return PublicArticleSearchOut(items=items, total=total, page=page, page_size=page_size)


async def record_article_view(
    article_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    visitor_id: str | None = Cookie(None),
) -> ViewRecordOut:
    exists = await session.scalar(select(Article.id).where(Article.id == article_id))
    if exists is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    if not visitor_id:
        visitor_seed = f"{request.headers.get('user-agent', '')}:{request.client.host if request.client else ''}"
        visitor_id = hashlib.sha256(visitor_seed.encode()).hexdigest()
        response.set_cookie("visitor_id", visitor_id, httponly=True, samesite="lax", max_age=31536000)
    today = date.today()
    visitor_hash = hash_visitor(f"{article_id}:{today}:{visitor_id}")
    insert_dedup = (
        insert(ArticleViewDedup)
        .values(article_id=article_id, view_date=today, visitor_key_hash=visitor_hash)
        .on_conflict_do_nothing()
    )
    result = await session.execute(insert_dedup)
    unique_increment = 1 if result.rowcount else 0
    insert_daily = (
        insert(ArticleViewDaily)
        .values(article_id=article_id, view_date=today, view_count=1, unique_view_count=unique_increment)
        .on_conflict_do_update(
            index_elements=["article_id", "view_date"],
            set_={
                "view_count": ArticleViewDaily.view_count + 1,
                "unique_view_count": ArticleViewDaily.unique_view_count + unique_increment,
            },
        )
    )
    await session.execute(insert_daily)
    await session.execute(update(Article).where(Article.id == article_id).values(views_count=Article.views_count + 1))
    await session.commit()
    return ViewRecordOut(ok=True, unique=bool(unique_increment))


@router.post("/articles/{article_id}/view", response_model=ViewRecordOut)
async def record_view(
    article_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    visitor_id: str | None = Cookie(None),
) -> ViewRecordOut:
    return await record_article_view(article_id, request, response, session, visitor_id)


@router.post("/articles/{article_id}/views", response_model=ViewRecordOut)
async def record_views_legacy(
    article_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    visitor_id: str | None = Cookie(None),
) -> ViewRecordOut:
    return await record_article_view(article_id, request, response, session, visitor_id)


@router.post("/articles/{article_id}/likes", response_model=ActionOkOut)
async def like(article_id: str, session: SessionDep, visitor_id: str = Cookie("anonymous")) -> ActionOkOut:
    raise AppError("UNAUTHORIZED", "Login and verified email are required to like articles", 401)


@router.get("/articles/{article_id}/comments", response_model=list[CommentOut])
async def comments(article_id: str, session: SessionDep) -> list[CommentOut]:
    rows = (
        await session.execute(
            select(Comment).where(Comment.article_id == article_id, Comment.status == "approved").order_by(Comment.created_at.desc())
        )
    ).scalars().all()
    return [CommentOut(id=row.id, author_name=row.author_name, body=row.body, status=row.status, created_at=row.created_at) for row in rows]


@router.post("/articles/{article_id}/comments", response_model=CommentOut)
async def create_comment(article_id: str, payload: CommentCreate, session: SessionDep) -> CommentOut:
    raise AppError("UNAUTHORIZED", "Login and verified email are required to comment", 401)
