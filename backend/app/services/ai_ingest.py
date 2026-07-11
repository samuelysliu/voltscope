from __future__ import annotations

import asyncio
import hashlib
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html import escape
from typing import Iterable
from urllib.parse import urljoin
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models import AiArticleCandidate, AiIngestJob, AiSource, Article, ArticleTopic, ArticleTranslation, Author, Topic, User

LOCK_KEY = "ai_ingest:lock"
LOCK_SECONDS = 15 * 60
TAIPEI = ZoneInfo("Asia/Taipei")


@dataclass(frozen=True)
class SourceItem:
    url: str
    title: str
    excerpt: str | None = None
    published_at: datetime | None = None


def normalize_hash(url: str, title: str) -> str:
    normalized = f"{url.strip().lower()}::{title.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180] or "ai-article"


def text_excerpt(value: str | None, fallback: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", value or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:280] if clean else fallback


def rss_text(element: ElementTree.Element, names: Iterable[str]) -> str | None:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return None


def parse_source_date(value: str | None) -> datetime | None:
    if not value:
        return None
    with suppress(ValueError):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return None


def parse_feed(xml_text: str, base_url: str) -> list[SourceItem]:
    root = ElementTree.fromstring(xml_text)
    items = root.findall(".//item")
    if not items:
        items = root.findall(".//{http://www.w3.org/2005/Atom}entry")
    parsed: list[SourceItem] = []
    for item in items[:10]:
        title = rss_text(item, ["title", "{http://www.w3.org/2005/Atom}title"]) or "Untitled EV update"
        link = rss_text(item, ["link"])
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            link = atom_link.attrib.get("href") if atom_link is not None else None
        excerpt = rss_text(
            item,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://www.w3.org/2005/Atom}content",
            ],
        )
        published = rss_text(item, ["pubDate", "published", "{http://www.w3.org/2005/Atom}published"])
        parsed.append(
            SourceItem(
                url=urljoin(base_url, link or base_url),
                title=title[:500],
                excerpt=text_excerpt(excerpt, title),
                published_at=parse_source_date(published),
            )
        )
    return parsed


async def fetch_source_items(source: AiSource) -> list[SourceItem]:
    if source.rss_url:
        try:
            async with httpx.AsyncClient(timeout=8.0, follow_redirects=True) as client:
                response = await client.get(source.rss_url)
                response.raise_for_status()
            items = parse_feed(response.text, source.base_url)
            if items:
                return items
        except Exception:
            pass

    today = datetime.now(TAIPEI).strftime("%Y-%m-%d")
    return [
        SourceItem(
            url=f"{source.base_url.rstrip('/')}/voltscope-ai-candidate-{today}",
            title=f"{source.name} EV charging and smart mobility update",
            excerpt=f"VoltScope generated a review candidate from {source.name}. Editors should verify the source context before publishing.",
            published_at=datetime.now(UTC),
        )
    ]


async def get_default_author(session) -> Author:
    author = await session.scalar(select(Author).where(Author.slug == "editorial-team"))
    if author is None:
        author = Author(slug="editorial-team", display_name="Editorial Team")
        session.add(author)
        await session.flush()
    return author


async def get_system_admin(session) -> User:
    settings = get_settings()
    admin = await session.scalar(select(User).where(User.email == settings.default_admin_email))
    if admin is None:
        admin = await session.scalar(select(User).where(User.role == "admin"))
    if admin is None:
        raise AppError("ADMIN_NOT_FOUND", "Admin user is required for AI article creation", 500)
    return admin


async def pick_topic(session, title: str, excerpt: str | None) -> Topic | None:
    haystack = f"{title} {excerpt or ''}".lower()
    slug = "ev"
    if any(word in haystack for word in ["deal", "discount", "coupon", "tariff", "rate"]):
        slug = "charging-deals"
    elif any(word in haystack for word in ["station", "charger", "infrastructure", "network"]):
        slug = "charging-station"
    elif any(word in haystack for word in ["charge", "charging", "battery"]):
        slug = "charging"
    elif any(word in haystack for word in ["mobility", "software", "autonomous", "fleet"]):
        slug = "smart-mobility"
    return await session.scalar(select(Topic).where(Topic.slug == slug))


async def unique_slug(session, base: str, locale: str) -> str:
    candidate = slugify(base)
    for index in range(0, 50):
        slug = candidate if index == 0 else f"{candidate}-{index + 1}"
        exists = await session.scalar(select(ArticleTranslation.id).where(ArticleTranslation.locale == locale, ArticleTranslation.slug == slug))
        if exists is None:
            return slug
    return f"{candidate}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


def generated_article_content(candidate: AiArticleCandidate) -> dict[str, dict[str, str]]:
    source_name = escape(candidate.source_name)
    source_title = escape(candidate.source_title)
    source_url = escape(candidate.source_url)
    excerpt = escape(text_excerpt(candidate.raw_excerpt, candidate.source_title))

    zh_title = f"{candidate.source_title[:90]}\uff1aVoltScope \u65b0\u805e"
    zh_excerpt = (
        f"{candidate.source_name} \u91cb\u51fa\u8207\u300c{candidate.source_title[:70]}\u300d\u76f8\u95dc\u7684\u5e02\u5834\u8a0a\u606f\uff0c"
        "\u5f8c\u7e8c\u5c07\u5f71\u97ff\u96fb\u52d5\u8eca\u3001\u5145\u96fb\u6216\u667a\u6167\u79fb\u52d5\u7522\u696d\u7684\u89c0\u5bdf\u91cd\u9ede\u3002"
    )
    zh_html = (
        f"<p>{candidate.source_name} \u516c\u958b\u7684\u8cc7\u8a0a\u986f\u793a\uff0c\u300c{source_title}\u300d\u5df2\u6210\u70ba\u96fb\u52d5\u8eca\u3001\u5145\u96fb\u6216\u667a\u6167\u79fb\u52d5\u5e02\u5834\u9700\u8981\u8ffd\u8e64\u7684\u8b70\u984c\u3002VoltScope \u5c07\u9019\u7b46\u4f86\u6e90\u8cc7\u6599\u5efa\u7acb\u70ba\u65b0\u805e\u7a3f\uff0c\u4f9b\u7de8\u8f2f\u9032\u4e00\u6b65\u6838\u5c0d\u8207\u88dc\u5145\u3002</p>"
        f"<h2>\u4e8b\u4ef6\u80cc\u666f</h2><p>{excerpt}</p>"
        f"<h2>\u7522\u696d\u5f71\u97ff</h2><p>{source_title} "
        "\u53ef\u80fd\u53cd\u6620\u8eca\u5ee0\u7b56\u7565\u3001\u5145\u96fb\u670d\u52d9\u3001\u80fd\u6e90\u7ba1\u7406\u6216\u6d88\u8cbb\u8005\u63a1\u7528\u901f\u5ea6\u7684\u8b8a\u5316\u3002"
        "\u7de8\u8f2f\u767c\u5e03\u524d\u61c9\u88dc\u5145\u5730\u5340\u689d\u4ef6\u3001\u50f9\u683c\u6216\u653f\u7b56\u80cc\u666f\uff0c\u4e26\u78ba\u8a8d\u539f\u59cb\u4f86\u6e90\u3002</p>"
        f"<h2>\u4f86\u6e90</h2><p>\u672c\u6587\u4f9d\u64da <a href=\"{source_url}\" rel=\"nofollow noopener\">{source_name}</a> \u516c\u958b\u8cc7\u8a0a\u5efa\u7acb\u5f85\u5be9\u7a3f\u3002</p>"
    )

    en_title = f"{candidate.source_title[:90]}: VoltScope news report"
    en_excerpt = f"{candidate.source_name} has surfaced a development that VoltScope editors should assess for its EV, charging, or smart mobility impact."
    en_html = (
        f"<p>{source_name} published information connected to {source_title}. VoltScope is treating the item as a news report for editorial review because it may affect the EV, charging, or smart mobility market.</p>"
        f"<h2>Background</h2><p>{excerpt}</p>"
        f"<h2>Market impact</h2><p>{source_title} may signal a change in automaker strategy, charging operations, energy management, or consumer adoption. Editors should verify timing, location, pricing or policy context, and source accuracy before publishing.</p>"
        f"<h2>Source</h2><p>This draft is based on public information from <a href=\"{source_url}\" rel=\"nofollow noopener\">{source_name}</a>.</p>"
    )

    return {
        "zh-TW": {
            "title": zh_title,
            "excerpt": zh_excerpt,
            "html": zh_html,
            "text": f"{zh_excerpt} {candidate.raw_excerpt or candidate.source_title}",
        },
        "en": {
            "title": en_title,
            "excerpt": en_excerpt,
            "html": en_html,
            "text": f"{en_excerpt} {candidate.raw_excerpt or candidate.source_title}",
        },
    }


async def approve_candidate_as_article(session, candidate: AiArticleCandidate, admin: User) -> Article:
    if candidate.decision == "accepted":
        raise AppError("CANDIDATE_ALREADY_ACCEPTED", "Candidate has already been approved", 409)
    author = await get_default_author(session)
    settings = get_settings()
    now = datetime.now(UTC)
    status = "published" if settings.ai_auto_publish else "draft"
    article = Article(
        author_id=author.id,
        admin_author_id=admin.id,
        status=status,
        source_type="ai",
        primary_source_url=candidate.source_url,
        primary_source_name=candidate.source_name,
        hero_image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1400&q=80",
        thumbnail_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=900&q=80",
        og_image_url="https://images.unsplash.com/photo-1593941707882-a5bba14938c7?auto=format&fit=crop&w=1200&q=80",
        created_by=admin.id,
        updated_by=admin.id,
        published_at=now if status == "published" else None,
        first_published_at=now if status == "published" else None,
    )
    session.add(article)
    await session.flush()

    content = generated_article_content(candidate)
    en_slug = await unique_slug(session, candidate.source_title, "en")
    zh_slug = await unique_slug(session, candidate.source_title, "zh-TW")
    for locale, data in content.items():
        session.add(
            ArticleTranslation(
                article_id=article.id,
                locale=locale,
                title=data["title"],
                slug=zh_slug if locale == "zh-TW" else en_slug,
                excerpt=data["excerpt"],
                content_json={"type": "doc", "source": "ai_ingest"},
                content_html=data["html"],
                content_text=data["text"],
                seo_title=data["title"][:255],
                seo_description=data["excerpt"][:320],
                og_title=data["title"][:255],
                og_description=data["excerpt"][:320],
                translation_status=status,
            )
        )

    topic = await pick_topic(session, candidate.source_title, candidate.raw_excerpt)
    if topic is not None:
        session.add(ArticleTopic(article_id=article.id, topic_id=topic.id, is_primary=True))

    candidate.decision = "accepted"
    candidate.rejection_reason = None
    await session.flush()
    return article


async def run_ai_ingest(session, auto_approve: bool | None = None) -> AiIngestJob:
    settings = get_settings()
    redis = get_redis()
    lock_acquired = False
    try:
        lock_acquired = bool(await redis.set(LOCK_KEY, "1", ex=LOCK_SECONDS, nx=True))
    except Exception:
        lock_acquired = True
    if not lock_acquired:
        raise AppError("AI_JOB_LOCKED", "Another AI ingest job is already running", 409)

    job = AiIngestJob(status="running", started_at=datetime.now(UTC))
    session.add(job)
    await session.flush()
    try:
        sources = (await session.execute(select(AiSource).where(AiSource.is_active.is_(True)).order_by(AiSource.created_at.desc()))).scalars().all()
        if not sources:
            sources = [
                AiSource(
                    name="VoltScope Seed Source",
                    base_url="https://example.com/voltscope-ai",
                    source_type="website",
                    is_active=True,
                )
            ]
            session.add_all(sources)
            await session.flush()

        new_candidates: list[AiArticleCandidate] = []
        for source in sources:
            for item in await fetch_source_items(source):
                item_hash = normalize_hash(item.url, item.title)
                exists = await session.scalar(select(AiArticleCandidate.id).where(AiArticleCandidate.normalized_hash == item_hash))
                if exists is not None:
                    continue
                candidate = AiArticleCandidate(
                    job_id=job.id,
                    source_url=item.url,
                    source_title=item.title,
                    source_name=source.name,
                    source_published_at=item.published_at,
                    raw_excerpt=text_excerpt(item.excerpt, item.title),
                    normalized_hash=item_hash,
                    decision="pending",
                )
                session.add(candidate)
                new_candidates.append(candidate)

        should_auto_approve = auto_approve if auto_approve is not None else settings.ai_auto_publish
        if should_auto_approve:
            admin = await get_system_admin(session)
            for candidate in new_candidates:
                await approve_candidate_as_article(session, candidate, admin)

        job.status = "completed"
        job.finished_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(job)
        return job
    except Exception as exc:
        job.status = "failed"
        job.error_message = str(exc)[:4000]
        job.finished_at = datetime.now(UTC)
        await session.commit()
        raise
    finally:
        with suppress(Exception):
            if lock_acquired:
                await redis.delete(LOCK_KEY)
            await redis.aclose()


def seconds_until_next_daily_run() -> float:
    now = datetime.now(TAIPEI)
    target = now.replace(hour=3, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return max((target - now).total_seconds(), 60)


async def ai_scheduler_loop() -> None:
    while True:
        await asyncio.sleep(seconds_until_next_daily_run())
        async with AsyncSessionLocal() as session:
            with suppress(Exception):
                await run_ai_ingest(session)
