import asyncio
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
from app.services.content_pipeline.candidates import crawl_source_to_candidates, select_quota_candidates

LOCK_SECONDS = 60 * 60


@dataclass
class PipelineRunResult:
    report: DailyContentReport
    generated_article_ids: list[str] = field(default_factory=list)
    selected_candidate_ids: list[str] = field(default_factory=list)
    skipped: bool = False


def lock_key(report_date: date) -> str:
    return f"lock:content_pipeline:daily:{report_date.isoformat()}"


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


async def run_scheduled_publish(session: AsyncSession) -> int:
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(Article).where(
                Article.status == "draft",
                Article.scheduled_at.is_not(None),
                Article.scheduled_at <= now,
                Article.deleted_at.is_(None),
            )
        )
    ).scalars().all()
    for article in rows:
        article.status = "published"
        article.published_at = article.published_at or now
        article.first_published_at = article.first_published_at or article.published_at
        translations = (await session.execute(select(ArticleTranslation).where(ArticleTranslation.article_id == article.id))).scalars().all()
        for translation in translations:
            translation.translation_status = "published"
    return len(rows)


async def run_daily_content_pipeline(
    session: AsyncSession,
    report_date: date | None = None,
    force: bool = False,
    dry_run: bool = False,
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
        sources = (
            await session.execute(
                select(SourceWhitelist).where(SourceWhitelist.enabled.is_(True)).order_by(SourceWhitelist.quota_role.asc(), SourceWhitelist.updated_at.desc())
            )
        ).scalars().all()
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

        for source in sources:
            try:
                await crawl_source_to_candidates(session, source.id)
            except Exception as exc:
                failed_sources.append({"id": source.id, "name": source.name, "error": str(exc)[:500]})

        selected = await select_quota_candidates(
            session,
            settings.content_pipeline_daily_taiwan_media_min,
            settings.content_pipeline_daily_international_min,
            settings.content_pipeline_daily_min_articles,
        )
        generated_articles: list[Article] = []
        generated_ids: list[str] = []
        if not dry_run:
            admin = await get_pipeline_admin(session)
            for candidate in selected:
                try:
                    result = await generate_article_from_candidate(session, candidate.id, admin)
                    generated_articles.append(result.article)
                    generated_ids.append(result.article.id)
                except Exception as exc:
                    candidate.decision = "failed"
                    candidate.rejection_reason = "generation_failed"
                    failed_sources.append({"candidate_id": candidate.id, "source_id": candidate.source_id, "error": str(exc)[:500]})

        degraded_rows = (
            await session.execute(select(SourceWhitelist).where(SourceWhitelist.health_status.in_(["degraded", "failed"])))
        ).scalars().all()
        degraded_sources.extend(
            {"id": source.id, "name": source.name, "health_status": source.health_status, "consecutive_failures": source.consecutive_failures}
            for source in degraded_rows
        )

        counts = report_counts(selected, generated_articles)
        quota_met = (
            counts["taiwan_media_count"] >= settings.content_pipeline_daily_taiwan_media_min
            and counts["international_count"] >= settings.content_pipeline_daily_international_min
            and len(selected) >= settings.content_pipeline_daily_min_articles
        )
        status = "success" if quota_met and not failed_sources and not dry_run else "warning"
        if not selected:
            status = "failed"
        quota_detail = {
            "dry_run": dry_run,
            "selected_candidate_ids": [item.id for item in selected],
            "selected_total": len(selected),
            "daily_min_articles": settings.content_pipeline_daily_min_articles,
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
                "message": "Dry run completed." if dry_run else "Daily content pipeline completed.",
            },
        )
        await session.commit()
        await session.refresh(report)
        return PipelineRunResult(
            report=report,
            generated_article_ids=generated_ids,
            selected_candidate_ids=[item.id for item in selected],
        )
    finally:
        with suppress(Exception):
            if acquired and not force:
                await redis.delete(lock_key(target_date))
            await redis.aclose()


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
