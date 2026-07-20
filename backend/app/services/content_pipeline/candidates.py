import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ContentCandidate, SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawledCandidate
from app.services.content_pipeline.source_crawler import test_crawl_source

TRACKING_PARAMS = {
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "utm_campaign",
    "utm_content",
    "utm_medium",
    "utm_source",
    "utm_term",
}

CORE_KEYWORDS = {
    "battery",
    "charge",
    "charger",
    "charging",
    "electric",
    "energy",
    "ev",
    "fleet",
    "grid",
    "infrastructure",
    "mobility",
    "software",
    "station",
    "vehicle",
}

QUOTA_BY_ROLE = {
    "taiwan_daily": "taiwan_media",
    "international_daily": "international_media",
    "event_driven": "event_driven",
    "reference_only": "reference_only",
}


@dataclass
class CandidateIngestResult:
    source: SourceWhitelist
    crawler_run_id: str
    created: list[ContentCandidate]
    duplicates: int
    rejected: int


def canonicalize_url(value: str) -> str:
    parsed = urlparse(value.strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query_pairs = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=False)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith("utm_")
    ]
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def normalized_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def quota_category(source: SourceWhitelist) -> str:
    return QUOTA_BY_ROLE.get(source.quota_role, source.source_group if source.source_group in QUOTA_BY_ROLE.values() else "reference_only")


def _haystack(candidate: CrawledCandidate) -> str:
    return f"{candidate.title} {candidate.excerpt or ''} {candidate.source_url}".lower()


def relevance_score(source: SourceWhitelist, candidate: CrawledCandidate) -> float:
    text = _haystack(candidate)
    allowed_topics = {topic.lower() for topic in (source.allowed_topics or [])}
    keyword_hits = sum(1 for keyword in CORE_KEYWORDS if keyword.lower() in text)
    topic_hits = sum(1 for topic in allowed_topics if topic and topic in text)
    score = 0.2 + min(keyword_hits * 0.08, 0.4) + min(topic_hits * 0.12, 0.24)
    if source.trust_level == "high":
        score += 0.12
    elif source.trust_level == "medium":
        score += 0.06
    published_at = ensure_aware(candidate.published_at)
    if published_at and published_at >= datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0):
        score += 0.08
    if candidate.parser_type == "rss":
        score += 0.08
    return round(max(0.0, min(score, 1.0)), 4)


async def novelty_score(session: AsyncSession, source: SourceWhitelist, canonical_url: str) -> float:
    digest = normalized_hash(canonical_url)
    same_source = await session.scalar(
        select(ContentCandidate.id).where(ContentCandidate.source_id == source.id, ContentCandidate.normalized_hash == digest).limit(1)
    )
    if same_source:
        return 0.0
    same_url = await session.scalar(select(ContentCandidate.id).where(ContentCandidate.canonical_url == canonical_url).limit(1))
    return 0.35 if same_url else 1.0


def raw_excerpt(candidate: CrawledCandidate) -> str | None:
    text = " ".join((candidate.excerpt or candidate.title).split())
    return text[:1000] if text else None


def ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def create_candidate_from_crawl(
    session: AsyncSession,
    source: SourceWhitelist,
    crawler_run_id: str,
    candidate: CrawledCandidate,
) -> ContentCandidate | None:
    canonical_url = canonicalize_url(candidate.source_url)
    digest = normalized_hash(canonical_url)
    existing = await session.scalar(
        select(ContentCandidate).where(ContentCandidate.source_id == source.id, ContentCandidate.normalized_hash == digest).limit(1)
    )
    if existing is not None:
        if existing.decision == "failed" and existing.rejection_reason == "generation_failed":
            existing.decision = "pending"
            existing.rejection_reason = None
            existing.fetched_at = datetime.now(UTC)
        return None
    fetched_at = datetime.now(UTC)
    item = ContentCandidate(
        crawler_run_id=crawler_run_id,
        source_id=source.id,
        source_url=candidate.source_url,
        canonical_url=canonical_url,
        source_title=candidate.title,
        source_excerpt=candidate.excerpt,
        source_author=candidate.author,
        source_published_at=ensure_aware(candidate.published_at),
        fetched_at=fetched_at,
        normalized_hash=digest,
        raw_text_excerpt=raw_excerpt(candidate),
        factual_notes=None,
        relevance_score=relevance_score(source, candidate),
        novelty_score=await novelty_score(session, source, canonical_url),
        quota_category=quota_category(source),
        decision="pending",
    )
    session.add(item)
    return item


async def crawl_source_to_candidates(
    session: AsyncSession,
    source_id: str,
    candidate_limit: int | None = None,
) -> CandidateIngestResult:
    crawl_result = await test_crawl_source(session, source_id, candidate_limit)
    source = crawl_result.source
    created: list[ContentCandidate] = []
    duplicates = 0
    rejected = 0
    for crawled in crawl_result.candidates:
        item = await create_candidate_from_crawl(session, source, crawl_result.run.id, crawled)
        if item is None:
            duplicates += 1
            continue
        if (item.relevance_score or 0) < 0.25:
            item.decision = "rejected"
            item.rejection_reason = "low_relevance"
            rejected += 1
        created.append(item)
    crawl_result.run.candidates_accepted = len([item for item in created if item.decision != "rejected"])
    await session.commit()
    for item in created:
        await session.refresh(item)
    await session.refresh(source)
    return CandidateIngestResult(
        source=source,
        crawler_run_id=crawl_result.run.id,
        created=created,
        duplicates=duplicates,
        rejected=rejected,
    )


async def select_quota_candidates(
    session: AsyncSession,
    taiwan_min: int = 1,
    international_min: int = 2,
    total_min: int = 3,
) -> list[ContentCandidate]:
    candidates = await rank_quota_candidates(session, taiwan_min, international_min)
    return candidates[:total_min]


async def rank_quota_candidates(
    session: AsyncSession,
    taiwan_min: int = 1,
    international_min: int = 2,
    source_id: str | None = None,
) -> list[ContentCandidate]:
    stmt = (
        select(ContentCandidate)
        .where(ContentCandidate.decision == "pending")
        .order_by(ContentCandidate.relevance_score.desc(), ContentCandidate.novelty_score.desc(), ContentCandidate.created_at.desc())
    )
    if source_id:
        stmt = stmt.where(ContentCandidate.source_id == source_id)
    candidates = (await session.execute(stmt)).scalars().all()
    selected: list[ContentCandidate] = []

    def take(category: str, count: int) -> None:
        for item in candidates:
            if len([row for row in selected if row.quota_category == category]) >= count:
                break
            if item.quota_category == category and item not in selected:
                selected.append(item)

    take("taiwan_media", taiwan_min)
    take("international_media", international_min)
    for item in candidates:
        if item not in selected:
            selected.append(item)
    return selected
