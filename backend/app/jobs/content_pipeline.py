import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import AsyncSessionLocal
from app.models import Article, ArticleTranslation, ContentCandidate, DailyContentReport, SourceWhitelist, User
from app.services.content_pipeline.ai.article_generator import generate_article_from_candidate
from app.services.content_pipeline.candidates import crawl_source_to_candidates, rank_quota_candidates

LOCK_SECONDS = 60 * 60
TRANSIENT_FAILURE_LIMIT = 3
logger = logging.getLogger(__name__)

TRANSIENT_ERROR_MARKERS = (
    "connection",
    "dns",
    "name or service not known",
    "network",
    "rate limit",
    "server disconnected",
    "temporary failure",
    "timed out",
    "timeout",
    "too many requests",
)


@dataclass
class PipelineRunResult:
    report: DailyContentReport
    generated_article_ids: list[str] = field(default_factory=list)
    selected_candidate_ids: list[str] = field(default_factory=list)
    skipped: bool = False


def lock_key(report_date: date) -> str:
    return f"lock:content_pipeline:daily:{report_date.isoformat()}"


def pipeline_error_details(exc: Exception) -> tuple[str, str, object]:
    if isinstance(exc, AppError):
        return exc.code, exc.message, exc.details
    return type(exc).__name__, str(exc).strip() or type(exc).__name__, None


def is_retryable_pipeline_error(exc: Exception) -> bool:
    code, message, details = pipeline_error_details(exc)
    if code not in {"SOURCE_ARTICLE_FETCH_FAILED", "AI_GENERATION_FAILED"}:
        return False
    searchable = f"{message} {details}".lower()
    return any(marker in searchable for marker in TRANSIENT_ERROR_MARKERS)


def serialize_pipeline_error(exc: Exception) -> dict:
    code, message, details = pipeline_error_details(exc)
    return {
        "code": code,
        "message": message[:500],
        "details": details,
        "retryable": is_retryable_pipeline_error(exc),
    }


async def get_pipeline_admin(session: AsyncSession) -> User:
    settings = get_settings()
    admin = await session.scalar(select(User).where(User.email == settings.default_admin_email, User.role == "admin"))
    if admin is None:
        admin = await session.scalar(select(User).where(User.role == "admin"))
    if admin is None:
        raise AppError("ADMIN_NOT_FOUND", "Admin user is required for content pipeline generation", 500)
    return admin


async def upsert_report(session: AsyncSession, report_date: date, values: dict) -> DailyContentReport:
    payload = {
        "report_date": report_date,
        "status": values.get("status", "warning"),
        "total_published": values.get("total_published", 0),
        "total_ready_for_review": values.get("total_ready_for_review", 0),
        "taiwan_media_count": values.get("taiwan_media_count", 0),
        "international_count": values.get("international_count", 0),
        "event_driven_count": values.get("event_driven_count", 0),
        "quota_met": values.get("quota_met", False),
        "quota_detail": values.get("quota_detail", {}),
        "failed_sources": values.get("failed_sources"),
        "degraded_sources": values.get("degraded_sources"),
        "message": values.get("message"),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    stmt = insert(DailyContentReport).values(**payload)
    update_values = {key: payload[key] for key in payload if key not in {"report_date", "created_at"}}
    stmt = stmt.on_conflict_do_update(index_elements=[DailyContentReport.report_date], set_=update_values).returning(DailyContentReport.id)
    report_id = await session.scalar(stmt)
    await session.flush()
    report = await session.get(DailyContentReport, report_id)
    if report is None:
        raise AppError("DAILY_REPORT_NOT_FOUND", "Daily report was not created", 500)
    return report


def report_counts(candidates: list[ContentCandidate], generated_articles: list[Article]) -> dict:
    published_ids = {article.id for article in generated_articles if article.status == "published"}
    ready_ids = {article.id for article in generated_articles if article.status != "published"}
    selected_by_category = {
        "taiwan_media": len([item for item in candidates if item.quota_category == "taiwan_media"]),
        "international_media": len([item for item in candidates if item.quota_category == "international_media"]),
        "event_driven": len([item for item in candidates if item.quota_category == "event_driven"]),
    }
    return {
        "total_published": len(published_ids),
        "total_ready_for_review": len(ready_ids),
        "taiwan_media_count": selected_by_category["taiwan_media"],
        "international_count": selected_by_category["international_media"],
        "event_driven_count": selected_by_category["event_driven"],
    }


def limit_generation_candidates(
    candidates: list[ContentCandidate],
    generation_target: int,
    manual_run: bool,
) -> list[ContentCandidate]:
    if not manual_run:
        return candidates
    return candidates[:generation_target]


def next_generation_candidate(
    candidates: list[ContentCandidate],
    attempted_ids: set[str],
    successful_candidates: list[ContentCandidate],
    taiwan_min: int,
    international_min: int,
) -> ContentCandidate | None:
    remaining = [candidate for candidate in candidates if candidate.id not in attempted_ids]
    if not remaining:
        return None
    taiwan_successes = len([candidate for candidate in successful_candidates if candidate.quota_category == "taiwan_media"])
    international_successes = len([candidate for candidate in successful_candidates if candidate.quota_category == "international_media"])
    preferred_category = None
    if taiwan_successes < taiwan_min:
        preferred_category = "taiwan_media"
    elif international_successes < international_min:
        preferred_category = "international_media"
    if preferred_category:
        preferred = next((candidate for candidate in remaining if candidate.quota_category == preferred_category), None)
        if preferred is not None:
            return preferred
    return remaining[0]


async def run_scheduled_publish(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(Article).where(
                    Article.status == "draft",
                    Article.scheduled_at.is_not(None),
                    Article.scheduled_at <= now,
                    Article.deleted_at.is_(None),
                )
            )
        )
        .scalars()
        .all()
    )
    for article in rows:
        article.status = "published"
        article.published_at = article.published_at or now
        article.first_published_at = article.first_published_at or article.published_at
        translations = (
            (await session.execute(select(ArticleTranslation).where(ArticleTranslation.article_id == article.id))).scalars().all()
        )
        for translation in translations:
            translation.translation_status = "published"
    return len(rows)


async def run_daily_content_pipeline(
    session: AsyncSession,
    report_date: date | None = None,
    force: bool = False,
    dry_run: bool = False,
    source_id: str | None = None,
    article_count: int | None = None,
) -> PipelineRunResult:
    settings = get_settings()
    if not dry_run and not settings.mistral_api_key.strip():
        raise AppError("AI_PROVIDER_NOT_CONFIGURED", "Mistral API key is not configured", 503)
    target_date = report_date or datetime.now(ZoneInfo(settings.content_pipeline_timezone)).date()
    redis = get_redis()
    acquired = False
    try:
        if not force:
            acquired = bool(await redis.set(lock_key(target_date), "1", ex=LOCK_SECONDS, nx=True))
            if not acquired:
                report = await upsert_report(
                    session,
                    target_date,
                    {
                        "status": "warning",
                        "quota_detail": {"skipped": "lock_exists"},
                        "message": "Daily content pipeline skipped because a lock already exists.",
                    },
                )
                await session.commit()
                return PipelineRunResult(report=report, skipped=True)
        else:
            acquired = True

        await run_scheduled_publish(session)
        source_stmt = select(SourceWhitelist).where(SourceWhitelist.enabled.is_(True))
        if source_id:
            source_stmt = source_stmt.where(SourceWhitelist.id == source_id)
        source_stmt = source_stmt.order_by(SourceWhitelist.quota_role.asc(), SourceWhitelist.updated_at.desc())
        sources = (await session.execute(source_stmt)).scalars().all()
        if not sources:
            report = await upsert_report(
                session,
                target_date,
                {
                    "status": "failed",
                    "quota_detail": {"error": "no_enabled_sources"},
                    "message": "No enabled content sources. Enable or create sources before running AI ingest.",
                },
            )
            await session.commit()
            await session.refresh(report)
            return PipelineRunResult(report=report)

        failed_sources: list[dict] = []
        degraded_sources: list[dict] = []
        crawled_candidate_total = 0
        remaining_crawl_target = article_count

        for source in sources:
            if remaining_crawl_target is not None and remaining_crawl_target <= 0:
                break
            try:
                crawl_result = await crawl_source_to_candidates(
                    session,
                    source.id,
                    candidate_limit=remaining_crawl_target,
                )
                crawled_count = len(crawl_result.created) + crawl_result.duplicates
                crawled_candidate_total += crawled_count
                if remaining_crawl_target is not None:
                    remaining_crawl_target -= crawled_count
            except Exception as exc:
                failed_sources.append({"id": source.id, "name": source.name, "error": str(exc)[:500]})

        candidate_pool = await rank_quota_candidates(
            session,
            settings.content_pipeline_daily_taiwan_media_min,
            settings.content_pipeline_daily_international_min,
            source_id=source_id,
        )
        generation_target = article_count or settings.content_pipeline_daily_min_articles
        custom_manual_target = source_id is not None or article_count is not None
        candidate_pool = limit_generation_candidates(candidate_pool, generation_target, custom_manual_target)
        generated_articles: list[Article] = []
        generated_ids: list[str] = []
        attempted_candidates: list[ContentCandidate] = []
        successful_candidates: list[ContentCandidate] = []
        generation_failures: list[dict] = []
        consecutive_retryable_failures = 0
        aborted_reason: str | None = None
        if not dry_run:
            admin = await get_pipeline_admin(session)
            attempted_ids: set[str] = set()
            while len(generated_articles) < generation_target:
                candidate = next_generation_candidate(
                    candidate_pool,
                    attempted_ids,
                    successful_candidates,
                    settings.content_pipeline_daily_taiwan_media_min,
                    settings.content_pipeline_daily_international_min,
                )
                if candidate is None:
                    break
                attempted_ids.add(candidate.id)
                attempted_candidates.append(candidate)
                try:
                    result = await generate_article_from_candidate(session, candidate.id, admin)
                    generated_articles.append(result.article)
                    generated_ids.append(result.article.id)
                    successful_candidates.append(candidate)
                    consecutive_retryable_failures = 0
                except Exception as exc:
                    error = serialize_pipeline_error(exc)
                    if error["retryable"]:
                        candidate.decision = "pending"
                        candidate.rejection_reason = None
                        consecutive_retryable_failures += 1
                    else:
                        candidate.decision = "failed"
                        candidate.rejection_reason = candidate.rejection_reason or "generation_failed"
                    generation_failures.append({"candidate_id": candidate.id, "source_id": candidate.source_id, "error": error})
                    if consecutive_retryable_failures >= TRANSIENT_FAILURE_LIMIT:
                        aborted_reason = "repeated_transient_generation_failures"
                        break
        else:
            attempted_candidates = candidate_pool[:generation_target]

        degraded_rows = (
            (await session.execute(select(SourceWhitelist).where(SourceWhitelist.health_status.in_(["degraded", "failed"]))))
            .scalars()
            .all()
        )
        degraded_sources.extend(
            {
                "id": source.id,
                "name": source.name,
                "health_status": source.health_status,
                "consecutive_failures": source.consecutive_failures,
            }
            for source in degraded_rows
        )

        counts = report_counts(successful_candidates, generated_articles)
        quota_met = (
            len(generated_articles) >= generation_target
            if custom_manual_target
            else counts["taiwan_media_count"] >= settings.content_pipeline_daily_taiwan_media_min
            and counts["international_count"] >= settings.content_pipeline_daily_international_min
            and len(generated_articles) >= generation_target
        )
        status = "success" if quota_met and not failed_sources and not dry_run else "warning"
        if not attempted_candidates:
            status = "failed"
        elif aborted_reason and not generated_articles:
            status = "failed"
        quota_detail = {
            "dry_run": dry_run,
            "candidate_pool_total": len(candidate_pool),
            "crawled_candidate_total": crawled_candidate_total,
            "attempted_candidate_ids": [item.id for item in attempted_candidates],
            "attempted_total": len(attempted_candidates),
            "successful_candidate_ids": [item.id for item in successful_candidates],
            "successful_total": len(generated_articles),
            "generation_failure_total": len(generation_failures),
            "generation_failures": generation_failures,
            "aborted_reason": aborted_reason,
            "daily_min_articles": generation_target,
            "requested_article_count": article_count,
            "selected_source_id": source_id,
            "taiwan_min": settings.content_pipeline_daily_taiwan_media_min,
            "international_min": settings.content_pipeline_daily_international_min,
            "generated_article_ids": generated_ids,
        }
        report = await upsert_report(
            session,
            target_date,
            {
                **counts,
                "status": status,
                "quota_met": quota_met,
                "quota_detail": quota_detail,
                "failed_sources": failed_sources or None,
                "degraded_sources": degraded_sources or None,
                "message": (
                    "Dry run completed."
                    if dry_run
                    else "Content pipeline stopped after repeated temporary network failures. Please retry later."
                    if aborted_reason
                    else "Daily content pipeline completed."
                ),
            },
        )
        await session.commit()
        await session.refresh(report)
        return PipelineRunResult(
            report=report,
            generated_article_ids=generated_ids,
            selected_candidate_ids=[item.id for item in attempted_candidates],
        )
    finally:
        with suppress(Exception):
            if acquired and not force:
                await redis.delete(lock_key(target_date))
            await redis.aclose()


async def run_manual_content_pipeline_background(
    run_id: str,
    report_date: date,
    force: bool,
    dry_run: bool,
    source_id: str | None = None,
    article_count: int | None = None,
) -> None:
    async with AsyncSessionLocal() as session:
        try:
            result = await run_daily_content_pipeline(session, report_date, force, dry_run, source_id, article_count)
            detail = dict(result.report.quota_detail or {})
            detail.update(
                {
                    "manual_run_id": run_id,
                    "trigger": "manual",
                    "selected_source_id": source_id,
                    "requested_article_count": article_count,
                }
            )
            result.report.quota_detail = detail
            await session.commit()
        except Exception as exc:
            logger.exception("Manual content pipeline failed", extra={"run_id": run_id, "report_date": str(report_date)})
            error = serialize_pipeline_error(exc)
            report = await upsert_report(
                session,
                report_date,
                {
                    "status": "failed",
                    "quota_detail": {
                        "manual_run_id": run_id,
                        "trigger": "manual",
                        "selected_source_id": source_id,
                        "requested_article_count": article_count,
                        "error": error,
                    },
                    "message": error["message"],
                },
            )
            await session.commit()
            await session.refresh(report)


def seconds_until_next_content_pipeline_run() -> float:
    settings = get_settings()
    now = datetime.now(ZoneInfo(settings.content_pipeline_timezone))
    target = now.replace(hour=settings.content_pipeline_daily_hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target + timedelta(days=1)
    return max((target - now).total_seconds(), 60)


async def content_pipeline_scheduler_loop() -> None:
    settings = get_settings()
    while True:
        await asyncio.sleep(seconds_until_next_content_pipeline_run())
        if not settings.content_pipeline_daily_enabled:
            continue
        async with AsyncSessionLocal() as session:
            with suppress(Exception):
                await run_daily_content_pipeline(session)
