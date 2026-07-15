from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, UploadFile
from sqlalchemy import Select, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.api.v1.deps import SessionDep, current_admin_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import (
    Ad,
    AiArticleCandidate,
    AiIngestJob,
    AiSource,
    Article,
    ArticleGenerationJob,
    ArticleTopic,
    ArticleTranslation,
    ArticleViewDaily,
    Author,
    Comment,
    ContentCandidate,
    CrawlerRun,
    DailyContentReport,
    EmailVerificationToken,
    MistralGenerationLog,
    SelectorRepairProposal,
    SourceParserVersion,
    SourceWhitelist,
    Topic,
    User,
)
from app.schemas.admin import (
    AdminAdOut,
    AdminAdPayload,
    AdminAiCandidateOut,
    AdminAiJobDetailOut,
    AdminAiJobOut,
    AdminAiRejectPayload,
    AdminAiSourceOut,
    AdminAiSourcePayload,
    AdminArticleGenerationJobOut,
    AdminCandidateGenerateOut,
    AdminCandidateIngestOut,
    AdminCandidateRejectPayload,
    AdminContentCandidateListOut,
    AdminContentCandidateOut,
    AdminContentPipelineMonitoringOut,
    AdminContentPipelineRunAcceptedOut,
    AdminContentPipelineRunPayload,
    AdminCrawlerCandidateOut,
    AdminCrawlerRunOut,
    AdminDailyContentReportListOut,
    AdminDailyContentReportOut,
    AdminContentSourceDetailOut,
    AdminContentSourceOut,
    AdminContentSourcePayload,
    AdminQuotaSelectionOut,
    AdminMistralGenerationLogOut,
    AdminSelectorRepairCreatePayload,
    AdminSelectorRepairProposalOut,
    AdminSelectorRepairRejectPayload,
    AdminFailedQualityGateOut,
    AdminTestCrawlOut,
    AdminSourceHealthOut,
    AdminSourceParserVersionPayload,
    AdminSourceParserVersionOut,
    AdminArticleListItem,
    AdminArticlePayload,
    AdminUserUpdate,
)
from app.schemas.content import ArticleTranslationIn
from app.services.ai_ingest import approve_candidate_as_article, run_ai_ingest
from app.jobs.content_pipeline import run_manual_content_pipeline_background, upsert_report
from app.services.content_pipeline.ai.article_generator import queue_article_generation, run_queued_article_generation
from app.services.content_pipeline.candidates import crawl_source_to_candidates, select_quota_candidates
from app.services.content_pipeline.crawlers.base import CrawledCandidate
from app.services.content_pipeline.selector_repair import (
    approve_parser_version,
    apply_selector_repair_proposal,
    create_selector_repair_proposal,
    next_parser_version,
    reject_selector_repair_proposal,
    validate_selector_config_for_source,
    validate_selector_repair_proposal,
)
from app.services.content_pipeline.source_crawler import test_crawl_source
from app.services.sanitize import sanitize_html

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(current_admin_user)])

ALLOWED_IMAGE_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif"}
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def get_default_author(session: SessionDep) -> Author:
    author = await session.scalar(select(Author).where(Author.slug == "editorial-team"))
    if author is None:
        author = Author(slug="editorial-team", display_name="Editorial Team")
        session.add(author)
        await session.flush()
    return author


async def serialize_article_item(article: Article) -> AdminArticleListItem:
    translation = next((item for item in article.translations if item.locale == "zh-TW"), None) or next(iter(article.translations), None)
    return AdminArticleListItem(
        id=article.id,
        status=article.status,
        is_featured=article.is_featured,
        show_ads=article.show_ads,
        created_at=article.created_at,
        updated_at=article.updated_at,
        published_at=article.published_at,
        title=translation.title if translation else "Untitled",
        slug=translation.slug if translation else "",
        excerpt=translation.excerpt if translation else "",
        locale=translation.locale if translation else "zh-TW",
        topics=[],
    )


def serialize_ad(ad: Ad) -> AdminAdOut:
    return AdminAdOut(
        id=ad.id,
        name=ad.name or ad.title,
        image_url=ad.image_url,
        target_url=ad.target_url,
        alt_text=ad.alt_text,
        placement=ad.placement or ad.placement_key,
        status="active" if ad.is_active else "inactive",
        starts_at=ad.starts_at,
        ends_at=ad.ends_at,
        weight=ad.weight,
    )


def serialize_ai_source(source: AiSource) -> AdminAiSourceOut:
    return AdminAiSourceOut(
        id=source.id,
        name=source.name,
        base_url=source.base_url,
        rss_url=source.rss_url,
        source_type=source.source_type,
        is_active=source.is_active,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def serialize_ai_candidate(candidate: AiArticleCandidate) -> AdminAiCandidateOut:
    return AdminAiCandidateOut(
        id=candidate.id,
        job_id=candidate.job_id,
        source_url=candidate.source_url,
        source_title=candidate.source_title,
        source_name=candidate.source_name,
        source_published_at=candidate.source_published_at,
        raw_excerpt=candidate.raw_excerpt,
        decision=candidate.decision,
        rejection_reason=candidate.rejection_reason,
        created_at=candidate.created_at,
    )


def content_source_domain(value: str) -> str:
    parsed = urlparse(value)
    domain = (parsed.netloc or parsed.path).lower().split("@")[-1].split(":")[0]
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain or "." not in domain:
        raise AppError("INVALID_SOURCE_DOMAIN", "Source URL must include a valid domain", 400)
    return domain


def serialize_parser_version(version: SourceParserVersion) -> AdminSourceParserVersionOut:
    return AdminSourceParserVersionOut(
        id=version.id,
        source_id=version.source_id,
        version=version.version,
        parser_type=version.parser_type,
        selector_config=version.selector_config,
        sample_url=version.sample_url,
        confidence_score=float(version.confidence_score) if version.confidence_score is not None else None,
        validation_status=version.validation_status,
        is_active=version.is_active,
        created_by=version.created_by,
        approved_by=version.approved_by,
        validation_result=version.validation_result,
        created_at=version.created_at,
        approved_at=version.approved_at,
        retired_at=version.retired_at,
    )


def serialize_selector_repair_proposal(proposal: SelectorRepairProposal, source_name: str | None = None) -> AdminSelectorRepairProposalOut:
    loaded_source = proposal.__dict__.get("source")
    return AdminSelectorRepairProposalOut(
        id=proposal.id,
        source_id=proposal.source_id,
        source_name=source_name or (loaded_source.name if loaded_source is not None else None),
        old_parser_version_id=proposal.old_parser_version_id,
        proposed_selector_config=proposal.proposed_selector_config,
        agent_reasoning_summary=proposal.agent_reasoning_summary,
        validation_result=proposal.validation_result,
        confidence_score=float(proposal.confidence_score) if proposal.confidence_score is not None else None,
        status=proposal.status,
        created_at=proposal.created_at,
        validated_at=proposal.validated_at,
        approved_at=proposal.approved_at,
        applied_at=proposal.applied_at,
    )


def serialize_crawler_run(run: CrawlerRun) -> AdminCrawlerRunOut:
    return AdminCrawlerRunOut(
        id=run.id,
        source_id=run.source_id,
        job_type=run.job_type,
        status=run.status,
        started_at=run.started_at,
        finished_at=run.finished_at,
        candidates_found=run.candidates_found,
        candidates_accepted=run.candidates_accepted,
        error_message=run.error_message,
        fallback_used=run.fallback_used,
        created_at=run.created_at,
    )


def serialize_crawler_candidate(candidate: CrawledCandidate) -> AdminCrawlerCandidateOut:
    return AdminCrawlerCandidateOut(
        source_url=candidate.source_url,
        title=candidate.title,
        excerpt=candidate.excerpt,
        published_at=candidate.published_at,
        author=candidate.author,
        parser_type=candidate.parser_type,
        confidence_score=candidate.confidence_score,
    )


def serialize_content_candidate(candidate: ContentCandidate, source_name: str | None = None) -> AdminContentCandidateOut:
    loaded_source = candidate.__dict__.get("source")
    return AdminContentCandidateOut(
        id=candidate.id,
        crawler_run_id=candidate.crawler_run_id,
        source_id=candidate.source_id,
        source_name=source_name or (loaded_source.name if loaded_source is not None else None),
        source_url=candidate.source_url,
        canonical_url=candidate.canonical_url,
        source_title=candidate.source_title,
        source_excerpt=candidate.source_excerpt,
        source_author=candidate.source_author,
        source_published_at=candidate.source_published_at,
        fetched_at=candidate.fetched_at,
        normalized_hash=candidate.normalized_hash,
        raw_text_excerpt=candidate.raw_text_excerpt,
        factual_notes=candidate.factual_notes,
        relevance_score=float(candidate.relevance_score) if candidate.relevance_score is not None else None,
        novelty_score=float(candidate.novelty_score) if candidate.novelty_score is not None else None,
        quota_category=candidate.quota_category,
        decision=candidate.decision,
        rejection_reason=candidate.rejection_reason,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def serialize_mistral_log(log: MistralGenerationLog) -> AdminMistralGenerationLogOut:
    return AdminMistralGenerationLogOut(
        id=log.id,
        generation_job_id=log.generation_job_id,
        purpose=log.purpose,
        model_name=log.model_name,
        prompt_version=log.prompt_version,
        input_token_count=log.input_token_count,
        output_token_count=log.output_token_count,
        latency_ms=log.latency_ms,
        status=log.status,
        error_message=log.error_message,
        created_at=log.created_at,
    )


def serialize_article_generation_job(job: ArticleGenerationJob, logs: list[MistralGenerationLog] | None = None) -> AdminArticleGenerationJobOut:
    return AdminArticleGenerationJobOut(
        id=job.id,
        candidate_id=job.candidate_id,
        status=job.status,
        provider=job.provider,
        model_name=job.model_name,
        prompt_version=job.prompt_version,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        retry_count=job.retry_count,
        quality_gate_result=job.quality_gate_result,
        generated_article_id=job.generated_article_id,
        created_at=job.created_at,
        logs=[serialize_mistral_log(log) for log in (logs or [])],
    )


def serialize_daily_content_report(report: DailyContentReport) -> AdminDailyContentReportOut:
    return AdminDailyContentReportOut(
        id=report.id,
        report_date=report.report_date,
        status=report.status,
        total_published=report.total_published,
        total_ready_for_review=report.total_ready_for_review,
        taiwan_media_count=report.taiwan_media_count,
        international_count=report.international_count,
        event_driven_count=report.event_driven_count,
        quota_met=report.quota_met,
        quota_detail=report.quota_detail or {},
        failed_sources=report.failed_sources,
        degraded_sources=report.degraded_sources,
        message=report.message,
        created_at=report.created_at,
        updated_at=report.updated_at,
    )


def serialize_source_health(source: SourceWhitelist) -> AdminSourceHealthOut:
    return AdminSourceHealthOut(
        id=source.id,
        name=source.name,
        domain=source.domain,
        enabled=source.enabled,
        quota_role=source.quota_role,
        health_status=source.health_status,
        consecutive_failures=source.consecutive_failures,
        last_success_at=source.last_success_at,
        last_failure_at=source.last_failure_at,
    )


def serialize_failed_quality_gate(job: ArticleGenerationJob) -> AdminFailedQualityGateOut:
    candidate = job.__dict__.get("candidate")
    source = candidate.__dict__.get("source") if candidate is not None else None
    return AdminFailedQualityGateOut(
        job_id=job.id,
        candidate_id=job.candidate_id,
        source_id=candidate.source_id if candidate is not None else "",
        source_name=source.name if source is not None else None,
        source_title=candidate.source_title if candidate is not None else "",
        status=job.status,
        error_message=job.error_message,
        quality_gate_result=job.quality_gate_result or {},
        created_at=job.created_at,
    )


def serialize_content_source(source: SourceWhitelist) -> AdminContentSourceOut:
    return AdminContentSourceOut(
        id=source.id,
        name=source.name,
        homepage_url=source.homepage_url,
        list_url=source.list_url,
        rss_url=source.rss_url,
        domain=source.domain,
        source_group=source.source_group,
        region=source.region,
        default_language=source.default_language,
        trust_level=source.trust_level,
        enabled=source.enabled,
        allowed_topics=source.allowed_topics or [],
        crawl_method=source.crawl_method,
        quota_role=source.quota_role,
        allow_auto_publish=source.allow_auto_publish,
        requires_review=source.requires_review,
        crawl_frequency_minutes=source.crawl_frequency_minutes,
        max_candidates_per_run=source.max_candidates_per_run,
        robots_checked_at=source.robots_checked_at,
        last_success_at=source.last_success_at,
        last_failure_at=source.last_failure_at,
        consecutive_failures=source.consecutive_failures,
        health_status=source.health_status,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


async def apply_content_source_payload(source: SourceWhitelist, payload: AdminContentSourcePayload) -> None:
    source.name = payload.name
    source.homepage_url = str(payload.homepage_url)
    source.list_url = str(payload.list_url) if payload.list_url else None
    source.rss_url = str(payload.rss_url) if payload.rss_url else None
    source.domain = content_source_domain(str(payload.homepage_url))
    source.source_group = payload.source_group
    source.region = payload.region
    source.default_language = payload.default_language
    source.trust_level = payload.trust_level
    source.enabled = payload.enabled
    source.allowed_topics = payload.allowed_topics
    source.crawl_method = payload.crawl_method
    source.quota_role = payload.quota_role
    source.allow_auto_publish = payload.allow_auto_publish
    source.requires_review = payload.requires_review
    source.crawl_frequency_minutes = payload.crawl_frequency_minutes
    source.max_candidates_per_run = payload.max_candidates_per_run
    source.health_status = "disabled" if not payload.enabled else "healthy"


async def serialize_ai_job(job: AiIngestJob, session: SessionDep, include_candidates: bool = False) -> AdminAiJobOut | AdminAiJobDetailOut:
    rows = (
        await session.execute(
            select(AiArticleCandidate.decision, func.count())
            .where(AiArticleCandidate.job_id == job.id)
            .group_by(AiArticleCandidate.decision)
        )
    ).all()
    counts = {decision: count for decision, count in rows}
    base = {
        "id": job.id,
        "status": job.status,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "candidate_count": sum(counts.values()),
        "pending_count": counts.get("pending", 0),
        "accepted_count": counts.get("accepted", 0),
        "rejected_count": counts.get("rejected", 0),
    }
    if not include_candidates:
        return AdminAiJobOut(**base)
    candidates = (
        await session.execute(select(AiArticleCandidate).where(AiArticleCandidate.job_id == job.id).order_by(AiArticleCandidate.created_at.desc()))
    ).scalars().all()
    return AdminAiJobDetailOut(**base, candidates=[serialize_ai_candidate(candidate) for candidate in candidates])


async def apply_article_payload(article: Article, payload: AdminArticlePayload, session: SessionDep, admin: User) -> None:
    author = await session.get(Author, payload.author_id) if payload.author_id else await get_default_author(session)
    if author is None:
        raise AppError("AUTHOR_NOT_FOUND", "Author not found", 404)
    was_published = article.status == "published"
    article.author_id = author.id
    article.status = payload.status
    article.is_featured = payload.is_featured
    article.show_ads = payload.show_ads
    article.hero_image_url = payload.hero_image_url
    article.thumbnail_url = payload.thumbnail_url or payload.hero_image_url
    article.og_image_url = payload.og_image_url or payload.hero_image_url
    article.updated_by = admin.id
    if payload.status == "published" and not was_published:
        article.published_at = datetime.now(UTC)
        article.first_published_at = article.first_published_at or article.published_at
    if payload.status != "published":
        article.published_at = None if payload.status == "draft" else article.published_at

    await release_deleted_article_slug_conflicts(article.id, payload.translations, session)

    existing_translation_rows = (
        await session.execute(select(ArticleTranslation).where(ArticleTranslation.article_id == article.id))
    ).scalars().all()
    existing_translations = {translation.locale: translation for translation in existing_translation_rows}
    incoming_locales = set()
    for item in payload.translations:
        incoming_locales.add(item.locale)
        translation = existing_translations.get(item.locale)
        if translation is None:
            translation = ArticleTranslation(article_id=article.id, locale=item.locale)
            session.add(translation)
        translation.title = item.title
        translation.slug = item.slug
        translation.excerpt = item.excerpt
        translation.content_json = item.content_json
        translation.content_html = sanitize_html(item.content_html)
        translation.content_text = item.content_text
        translation.seo_title = item.seo_title
        translation.seo_description = item.seo_description
        translation.og_title = item.og_title
        translation.og_description = item.og_description
        translation.translation_status = "published" if payload.status == "published" else item.translation_status

    for locale, translation in existing_translations.items():
        if locale not in incoming_locales:
            await session.delete(translation)

    await session.execute(delete(ArticleTopic).where(ArticleTopic.article_id == article.id))
    for index, topic_id in enumerate(payload.topic_ids):
        if await session.get(Topic, topic_id) is None:
            raise AppError("TOPIC_NOT_FOUND", "Topic not found", 404)
        session.add(ArticleTopic(article_id=article.id, topic_id=topic_id, is_primary=index == 0))


def released_article_slug(slug: str, translation_id: str) -> str:
    suffix = f"-deleted-{translation_id[:8]}"
    return f"{slug[: 220 - len(suffix)]}{suffix}"


async def release_deleted_article_slug_conflicts(
    article_id: str,
    translations: list[ArticleTranslationIn],
    session: SessionDep,
) -> None:
    released_conflict = False
    for item in translations:
        row = (
            await session.execute(
                select(ArticleTranslation, Article.deleted_at)
                .join(Article, Article.id == ArticleTranslation.article_id)
                .where(
                    ArticleTranslation.locale == item.locale,
                    ArticleTranslation.slug == item.slug,
                    ArticleTranslation.article_id != article_id,
                )
                .limit(1)
            )
        ).first()
        if row is None:
            continue
        conflicting_translation, deleted_at = row
        if deleted_at is None:
            raise AppError(
                "ARTICLE_SLUG_CONFLICT",
                "The article slug is already in use",
                409,
                {"locale": item.locale, "slug": item.slug},
            )
        conflicting_translation.slug = released_article_slug(
            conflicting_translation.slug,
            conflicting_translation.id,
        )
        released_conflict = True
    if released_conflict:
        await session.flush()


async def commit_article_changes(session: SessionDep) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if "article_translations_locale_slug_key" in str(exc):
            raise AppError("ARTICLE_SLUG_CONFLICT", "The article slug is already in use", 409) from exc
        raise


@router.get("/dashboard")
async def dashboard(session: SessionDep) -> dict:
    settings = get_settings()
    local_timezone = ZoneInfo(settings.content_pipeline_timezone)
    yesterday = datetime.now(local_timezone).date() - timedelta(days=1)
    yesterday_start = datetime.combine(yesterday, time.min, tzinfo=local_timezone).astimezone(UTC)
    yesterday_end = yesterday_start + timedelta(days=1)
    articles = await session.scalar(select(func.count()).select_from(Article).where(Article.deleted_at.is_(None)))
    published = await session.scalar(select(func.count()).select_from(Article).where(Article.status == "published", Article.deleted_at.is_(None)))
    drafts = await session.scalar(select(func.count()).select_from(Article).where(Article.status == "draft", Article.deleted_at.is_(None)))
    users = await session.scalar(select(func.count()).select_from(User))
    ads = await session.scalar(select(func.count()).select_from(Ad))
    today_views = await session.scalar(select(func.coalesce(func.sum(ArticleViewDaily.view_count), 0)).where(ArticleViewDaily.view_date == date.today()))
    crawler_status_rows = (
        await session.execute(
            select(CrawlerRun.status, func.count())
            .where(CrawlerRun.started_at >= yesterday_start, CrawlerRun.started_at < yesterday_end, CrawlerRun.job_type == "source_test")
            .group_by(CrawlerRun.status)
        )
    ).all()
    generation_status_rows = (
        await session.execute(
            select(ArticleGenerationJob.status, func.count())
            .where(ArticleGenerationJob.created_at >= yesterday_start, ArticleGenerationJob.created_at < yesterday_end)
            .group_by(ArticleGenerationJob.status)
        )
    ).all()
    report = await session.scalar(select(DailyContentReport).where(DailyContentReport.report_date == yesterday))
    crawler_counts = {status: count for status, count in crawler_status_rows}
    generation_counts = {status: count for status, count in generation_status_rows}
    return {
        "articles": articles or 0,
        "published_articles": published or 0,
        "draft_articles": drafts or 0,
        "users": users or 0,
        "ads": ads or 0,
        "today_views": today_views or 0,
        "yesterday_ai_schedule": {
            "date": yesterday,
            "status": report.status if report else "not_run",
            "crawl_success": crawler_counts.get("success", 0) + crawler_counts.get("partial_success", 0),
            "crawl_failed": crawler_counts.get("failed", 0),
            "generation_success": generation_counts.get("success", 0),
            "generation_failed": generation_counts.get("failed", 0),
        },
    }


@router.get("/content-sources", response_model=list[AdminContentSourceOut])
async def admin_content_sources(
    session: SessionDep,
    source_group: str | None = None,
    region: str | None = None,
    enabled: bool | None = None,
    health_status: str | None = None,
    quota_role: str | None = None,
) -> list[AdminContentSourceOut]:
    stmt = select(SourceWhitelist).order_by(SourceWhitelist.updated_at.desc())
    if source_group:
        stmt = stmt.where(SourceWhitelist.source_group == source_group)
    if region:
        stmt = stmt.where(SourceWhitelist.region == region)
    if enabled is not None:
        stmt = stmt.where(SourceWhitelist.enabled.is_(enabled))
    if health_status:
        stmt = stmt.where(SourceWhitelist.health_status == health_status)
    if quota_role:
        stmt = stmt.where(SourceWhitelist.quota_role == quota_role)
    rows = (await session.execute(stmt)).scalars().all()
    return [serialize_content_source(row) for row in rows]


@router.post("/content-sources", response_model=AdminContentSourceOut, status_code=201)
async def create_admin_content_source(payload: AdminContentSourcePayload, session: SessionDep) -> AdminContentSourceOut:
    source = SourceWhitelist()
    await apply_content_source_payload(source, payload)
    session.add(source)
    await session.flush()
    session.add(
        SourceParserVersion(
            source_id=source.id,
            version=1,
            parser_type=payload.crawl_method if payload.crawl_method != "hybrid" else "rss",
            selector_config={
                "rss_url": str(payload.rss_url) if payload.rss_url else None,
                "list_url": str(payload.list_url) if payload.list_url else None,
                "homepage_url": str(payload.homepage_url),
            },
            sample_url=str(payload.rss_url or payload.list_url or payload.homepage_url),
            confidence_score=1.0 if payload.rss_url else 0.5,
            validation_status="approved" if payload.rss_url else "draft",
            is_active=bool(payload.rss_url),
            created_by="admin",
            approved_at=datetime.now(UTC) if payload.rss_url else None,
        )
    )
    await session.commit()
    await session.refresh(source)
    return serialize_content_source(source)


@router.get("/content-sources/{source_id}", response_model=AdminContentSourceDetailOut)
async def admin_content_source_detail(source_id: str, session: SessionDep) -> AdminContentSourceDetailOut:
    source = await session.scalar(
        select(SourceWhitelist)
        .options(selectinload(SourceWhitelist.parser_versions))
        .where(SourceWhitelist.id == source_id)
    )
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    recent_runs = (
        await session.execute(
            select(CrawlerRun).where(CrawlerRun.source_id == source.id).order_by(CrawlerRun.created_at.desc()).limit(5)
        )
    ).scalars().all()
    data = serialize_content_source(source).model_dump()
    versions = sorted(source.parser_versions, key=lambda item: item.version, reverse=True)
    return AdminContentSourceDetailOut(
        **data,
        parser_versions=[serialize_parser_version(version) for version in versions],
        recent_crawler_runs=[serialize_crawler_run(run) for run in recent_runs],
    )


@router.get("/content-sources/{source_id}/parser-versions", response_model=list[AdminSourceParserVersionOut])
async def admin_content_source_parser_versions(source_id: str, session: SessionDep) -> list[AdminSourceParserVersionOut]:
    if await session.get(SourceWhitelist, source_id) is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    rows = (
        await session.execute(
            select(SourceParserVersion).where(SourceParserVersion.source_id == source_id).order_by(SourceParserVersion.version.desc())
        )
    ).scalars().all()
    return [serialize_parser_version(row) for row in rows]


@router.post("/content-sources/{source_id}/parser-versions", response_model=AdminSourceParserVersionOut, status_code=201)
async def create_admin_content_source_parser_version(
    source_id: str,
    payload: AdminSourceParserVersionPayload,
    session: SessionDep,
    admin: User = Depends(current_admin_user),
) -> AdminSourceParserVersionOut:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    now = datetime.now(UTC)
    version = SourceParserVersion(
        source_id=source.id,
        version=await next_parser_version(session, source.id),
        parser_type=payload.parser_type,
        selector_config=payload.selector_config,
        sample_url=payload.sample_url,
        confidence_score=payload.confidence_score,
        validation_status="approved" if payload.is_active else payload.validation_status,
        is_active=False,
        created_by="admin",
        approved_by=admin.id if payload.is_active else None,
        approved_at=now if payload.is_active else None,
    )
    session.add(version)
    await session.flush()
    if payload.is_active:
        await approve_parser_version(session, version, admin, validate_first=payload.parser_type == "html")
    await session.commit()
    await session.refresh(version)
    return serialize_parser_version(version)


@router.post("/parser-versions/{parser_version_id}/validate", response_model=AdminSourceParserVersionOut)
async def validate_admin_parser_version(parser_version_id: str, session: SessionDep) -> AdminSourceParserVersionOut:
    version = await session.get(SourceParserVersion, parser_version_id)
    if version is None:
        raise AppError("PARSER_VERSION_NOT_FOUND", "Parser version not found", 404)
    source = await session.get(SourceWhitelist, version.source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    if version.parser_type == "html":
        validation = await validate_selector_config_for_source(source, version.selector_config)
        version.validation_result = validation.result
        version.confidence_score = validation.confidence_score
        version.validation_status = "validated" if validation.result.get("passed") else "draft"
    else:
        version.validation_result = {"passed": True, "parser_type": version.parser_type, "validated_at": datetime.now(UTC).isoformat()}
        version.validation_status = "validated"
    await session.commit()
    await session.refresh(version)
    return serialize_parser_version(version)


@router.post("/parser-versions/{parser_version_id}/approve", response_model=AdminSourceParserVersionOut)
async def approve_admin_parser_version(
    parser_version_id: str,
    session: SessionDep,
    admin: User = Depends(current_admin_user),
) -> AdminSourceParserVersionOut:
    version = await session.get(SourceParserVersion, parser_version_id)
    if version is None:
        raise AppError("PARSER_VERSION_NOT_FOUND", "Parser version not found", 404)
    await approve_parser_version(session, version, admin, validate_first=version.parser_type == "html")
    await session.commit()
    await session.refresh(version)
    return serialize_parser_version(version)


@router.post("/parser-versions/{parser_version_id}/rollback", response_model=AdminSourceParserVersionOut)
async def rollback_admin_parser_version(
    parser_version_id: str,
    session: SessionDep,
    admin: User = Depends(current_admin_user),
) -> AdminSourceParserVersionOut:
    version = await session.get(SourceParserVersion, parser_version_id)
    if version is None:
        raise AppError("PARSER_VERSION_NOT_FOUND", "Parser version not found", 404)
    await approve_parser_version(session, version, admin, validate_first=False)
    version.validation_result = {**(version.validation_result or {}), "rollback_applied_at": datetime.now(UTC).isoformat()}
    await session.commit()
    await session.refresh(version)
    return serialize_parser_version(version)


@router.post("/content-sources/{source_id}/test-crawl", response_model=AdminTestCrawlOut)
async def test_admin_content_source_crawl(source_id: str, session: SessionDep) -> AdminTestCrawlOut:
    result = await test_crawl_source(session, source_id)
    run = serialize_crawler_run(result.run)
    return AdminTestCrawlOut(
        source=serialize_content_source(result.source),
        run=run,
        candidates=[serialize_crawler_candidate(candidate) for candidate in result.candidates],
        fallback_used=run.fallback_used,
    )


@router.put("/content-sources/{source_id}", response_model=AdminContentSourceOut)
async def update_admin_content_source(source_id: str, payload: AdminContentSourcePayload, session: SessionDep) -> AdminContentSourceOut:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    await apply_content_source_payload(source, payload)
    await session.commit()
    await session.refresh(source)
    return serialize_content_source(source)


@router.delete("/content-sources/{source_id}", response_model=AdminContentSourceOut)
async def delete_admin_content_source(source_id: str, session: SessionDep) -> AdminContentSourceOut:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    source.enabled = False
    source.health_status = "disabled"
    await session.commit()
    await session.refresh(source)
    return serialize_content_source(source)


@router.post("/content-sources/{source_id}/disable", response_model=AdminContentSourceOut)
async def disable_admin_content_source(source_id: str, session: SessionDep) -> AdminContentSourceOut:
    return await delete_admin_content_source(source_id, session)


@router.post("/content-sources/{source_id}/enable", response_model=AdminContentSourceOut)
async def enable_admin_content_source(source_id: str, session: SessionDep) -> AdminContentSourceOut:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)
    source.enabled = True
    source.health_status = "healthy"
    await session.commit()
    await session.refresh(source)
    return serialize_content_source(source)


@router.post("/content-sources/{source_id}/crawl-candidates", response_model=AdminCandidateIngestOut)
async def crawl_admin_content_source_candidates(source_id: str, session: SessionDep) -> AdminCandidateIngestOut:
    result = await crawl_source_to_candidates(session, source_id)
    return AdminCandidateIngestOut(
        source=serialize_content_source(result.source),
        crawler_run_id=result.crawler_run_id,
        created_count=len(result.created),
        duplicate_count=result.duplicates,
        rejected_count=result.rejected,
        candidates=[serialize_content_candidate(candidate, result.source.name) for candidate in result.created],
    )


@router.get("/selector-repair-proposals", response_model=list[AdminSelectorRepairProposalOut])
async def admin_selector_repair_proposals(
    session: SessionDep,
    source_id: str | None = None,
    status: str | None = None,
) -> list[AdminSelectorRepairProposalOut]:
    stmt = (
        select(SelectorRepairProposal)
        .options(selectinload(SelectorRepairProposal.source))
        .order_by(SelectorRepairProposal.created_at.desc())
    )
    if source_id:
        stmt = stmt.where(SelectorRepairProposal.source_id == source_id)
    if status:
        stmt = stmt.where(SelectorRepairProposal.status == status)
    stmt = stmt.limit(100)
    rows = (await session.execute(stmt)).scalars().all()
    return [serialize_selector_repair_proposal(row) for row in rows]


@router.post("/selector-repair-proposals", response_model=AdminSelectorRepairProposalOut, status_code=201)
async def create_admin_selector_repair_proposal(
    payload: AdminSelectorRepairCreatePayload,
    session: SessionDep,
) -> AdminSelectorRepairProposalOut:
    proposal = await create_selector_repair_proposal(session, payload.source_id)
    await session.commit()
    proposal = await session.scalar(
        select(SelectorRepairProposal).options(selectinload(SelectorRepairProposal.source)).where(SelectorRepairProposal.id == proposal.id)
    )
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    return serialize_selector_repair_proposal(proposal)


@router.get("/selector-repair-proposals/{proposal_id}", response_model=AdminSelectorRepairProposalOut)
async def admin_selector_repair_proposal_detail(proposal_id: str, session: SessionDep) -> AdminSelectorRepairProposalOut:
    proposal = await session.scalar(
        select(SelectorRepairProposal).options(selectinload(SelectorRepairProposal.source)).where(SelectorRepairProposal.id == proposal_id)
    )
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    return serialize_selector_repair_proposal(proposal)


@router.post("/selector-repair-proposals/{proposal_id}/validate", response_model=AdminSelectorRepairProposalOut)
async def validate_admin_selector_repair_proposal(proposal_id: str, session: SessionDep) -> AdminSelectorRepairProposalOut:
    proposal = await validate_selector_repair_proposal(session, proposal_id)
    await session.commit()
    proposal = await session.scalar(
        select(SelectorRepairProposal).options(selectinload(SelectorRepairProposal.source)).where(SelectorRepairProposal.id == proposal.id)
    )
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    return serialize_selector_repair_proposal(proposal)


@router.post("/selector-repair-proposals/{proposal_id}/approve", response_model=AdminSelectorRepairProposalOut)
async def approve_admin_selector_repair_proposal(
    proposal_id: str,
    session: SessionDep,
    admin: User = Depends(current_admin_user),
) -> AdminSelectorRepairProposalOut:
    proposal = await session.get(SelectorRepairProposal, proposal_id)
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    await apply_selector_repair_proposal(session, proposal, admin)
    await session.commit()
    proposal = await session.scalar(
        select(SelectorRepairProposal).options(selectinload(SelectorRepairProposal.source)).where(SelectorRepairProposal.id == proposal.id)
    )
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    return serialize_selector_repair_proposal(proposal)


@router.post("/selector-repair-proposals/{proposal_id}/reject", response_model=AdminSelectorRepairProposalOut)
async def reject_admin_selector_repair_proposal(
    proposal_id: str,
    payload: AdminSelectorRepairRejectPayload,
    session: SessionDep,
) -> AdminSelectorRepairProposalOut:
    proposal = await reject_selector_repair_proposal(session, proposal_id, payload.reason)
    await session.commit()
    proposal = await session.scalar(
        select(SelectorRepairProposal).options(selectinload(SelectorRepairProposal.source)).where(SelectorRepairProposal.id == proposal.id)
    )
    if proposal is None:
        raise AppError("SELECTOR_REPAIR_PROPOSAL_NOT_FOUND", "Selector repair proposal not found", 404)
    return serialize_selector_repair_proposal(proposal)


@router.post(
    "/content-pipeline/run-now",
    response_model=AdminContentPipelineRunAcceptedOut,
    status_code=202,
)
async def run_admin_content_pipeline(
    payload: AdminContentPipelineRunPayload,
    background_tasks: BackgroundTasks,
    session: SessionDep,
) -> AdminContentPipelineRunAcceptedOut:
    settings = get_settings()
    if not payload.dry_run and not settings.mistral_api_key.strip():
        raise AppError("AI_PROVIDER_NOT_CONFIGURED", "Mistral API key is not configured", 503)
    report_date = payload.date or datetime.now(ZoneInfo(settings.content_pipeline_timezone)).date()
    existing = await session.scalar(select(DailyContentReport).where(DailyContentReport.report_date == report_date))
    running_is_current = bool(
        existing is not None
        and existing.status == "running"
        and existing.updated_at >= datetime.now(UTC) - timedelta(hours=2)
    )
    if existing is not None and running_is_current:
        existing_run_id = str((existing.quota_detail or {}).get("manual_run_id") or existing.id)
        return AdminContentPipelineRunAcceptedOut(
            run_id=existing_run_id,
            report_date=report_date,
            status="running",
            already_running=True,
        )

    run_id = str(uuid4())
    await upsert_report(
        session,
        report_date,
        {
            "status": "running",
            "quota_detail": {
                "manual_run_id": run_id,
                "trigger": "manual",
                "dry_run": payload.dry_run,
            },
            "message": "Manual content pipeline queued.",
        },
    )
    await session.commit()
    background_tasks.add_task(
        run_manual_content_pipeline_background,
        run_id,
        report_date,
        payload.force,
        payload.dry_run,
    )
    return AdminContentPipelineRunAcceptedOut(
        run_id=run_id,
        report_date=report_date,
        status="queued",
    )


@router.get("/content-pipeline/monitoring", response_model=AdminContentPipelineMonitoringOut)
async def admin_content_pipeline_monitoring(session: SessionDep) -> AdminContentPipelineMonitoringOut:
    latest_report = await session.scalar(
        select(DailyContentReport).order_by(DailyContentReport.report_date.desc(), DailyContentReport.updated_at.desc()).limit(1)
    )
    quota_candidates = await select_quota_candidates(
        session,
        get_settings().content_pipeline_daily_taiwan_media_min,
        get_settings().content_pipeline_daily_international_min,
        get_settings().content_pipeline_daily_min_articles,
    )
    quota_items = [serialize_content_candidate(candidate) for candidate in quota_candidates]
    source_rows = (
        await session.execute(
            select(SourceWhitelist).order_by(SourceWhitelist.enabled.desc(), SourceWhitelist.health_status.asc(), SourceWhitelist.name.asc())
        )
    ).scalars().all()
    recent_jobs = (
        await session.execute(
            select(ArticleGenerationJob)
            .options(selectinload(ArticleGenerationJob.candidate).selectinload(ContentCandidate.source))
            .where(ArticleGenerationJob.quality_gate_result.is_not(None))
            .order_by(ArticleGenerationJob.created_at.desc())
            .limit(100)
        )
    ).scalars().all()
    failed_quality_gates = []
    for job in recent_jobs:
        gate = job.quality_gate_result or {}
        if gate.get("pass") is False or int(gate.get("critical_count") or 0) > 0 or gate.get("recommendation") == "failed_quality_gate":
            failed_quality_gates.append(serialize_failed_quality_gate(job))
        if len(failed_quality_gates) >= 20:
            break

    report_status_rows = (await session.execute(select(DailyContentReport.status, func.count()).group_by(DailyContentReport.status))).all()
    candidate_decision_rows = (await session.execute(select(ContentCandidate.decision, func.count()).group_by(ContentCandidate.decision))).all()
    return AdminContentPipelineMonitoringOut(
        latest_report=serialize_daily_content_report(latest_report) if latest_report is not None else None,
        quota_preview=AdminQuotaSelectionOut(
            candidates=quota_items,
            taiwan_count=len([item for item in quota_items if item.quota_category == "taiwan_media"]),
            international_count=len([item for item in quota_items if item.quota_category == "international_media"]),
            total_count=len(quota_items),
        ),
        source_health=[serialize_source_health(source) for source in source_rows],
        failed_quality_gates=failed_quality_gates,
        report_status_counts={str(status): int(count) for status, count in report_status_rows},
        candidate_decision_counts={str(decision): int(count) for decision, count in candidate_decision_rows},
    )


@router.get("/content-pipeline/reports", response_model=AdminDailyContentReportListOut)
async def admin_content_pipeline_reports(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> AdminDailyContentReportListOut:
    stmt = select(DailyContentReport).order_by(DailyContentReport.report_date.desc(), DailyContentReport.updated_at.desc())
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return AdminDailyContentReportListOut(
        items=[serialize_daily_content_report(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/content-pipeline/reports/{report_date}", response_model=AdminDailyContentReportOut)
async def admin_content_pipeline_report_detail(report_date: date, session: SessionDep) -> AdminDailyContentReportOut:
    report = await session.scalar(select(DailyContentReport).where(DailyContentReport.report_date == report_date))
    if report is None:
        raise AppError("DAILY_CONTENT_REPORT_NOT_FOUND", "Daily content report not found", 404)
    return serialize_daily_content_report(report)


@router.get("/content-pipeline/candidates", response_model=AdminContentCandidateListOut)
async def admin_content_pipeline_candidates(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_id: str | None = None,
    decision: str | None = None,
    quota_category: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AdminContentCandidateListOut:
    stmt = select(ContentCandidate).options(selectinload(ContentCandidate.source)).order_by(ContentCandidate.created_at.desc())
    if source_id:
        stmt = stmt.where(ContentCandidate.source_id == source_id)
    if decision == "pending":
        stmt = stmt.where(ContentCandidate.decision.in_(["pending", "accepted", "failed"]))
    elif decision == "generated":
        stmt = stmt.where(ContentCandidate.decision.in_(["generated", "published"]))
    elif decision == "rejected":
        stmt = stmt.where(ContentCandidate.decision == "rejected")
    elif decision:
        raise AppError("INVALID_CANDIDATE_STATUS", "Candidate status is invalid", 400)
    else:
        stmt = stmt.where(ContentCandidate.decision.in_(["pending", "accepted", "failed"]))
    if quota_category:
        stmt = stmt.where(ContentCandidate.quota_category == quota_category)
    if date_from:
        stmt = stmt.where(ContentCandidate.created_at >= date_from)
    if date_to:
        stmt = stmt.where(ContentCandidate.created_at <= date_to)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().all()
    return AdminContentCandidateListOut(
        items=[serialize_content_candidate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/content-pipeline/quota-selection", response_model=AdminQuotaSelectionOut)
async def admin_content_pipeline_quota_selection(session: SessionDep) -> AdminQuotaSelectionOut:
    candidates = await select_quota_candidates(session, get_settings().content_pipeline_daily_taiwan_media_min, get_settings().content_pipeline_daily_international_min, get_settings().content_pipeline_daily_min_articles)
    items = [serialize_content_candidate(candidate) for candidate in candidates]
    return AdminQuotaSelectionOut(
        candidates=items,
        taiwan_count=len([item for item in items if item.quota_category == "taiwan_media"]),
        international_count=len([item for item in items if item.quota_category == "international_media"]),
        total_count=len(items),
    )


@router.post("/content-pipeline/candidates/{candidate_id}/accept", response_model=AdminContentCandidateOut)
async def accept_admin_content_candidate(candidate_id: str, session: SessionDep) -> AdminContentCandidateOut:
    candidate = await session.get(ContentCandidate, candidate_id)
    if candidate is None:
        raise AppError("CONTENT_CANDIDATE_NOT_FOUND", "Content candidate not found", 404)
    if candidate.decision in {"generated", "published"}:
        raise AppError("CONTENT_CANDIDATE_LOCKED", "Generated or published candidates cannot be accepted again", 409)
    candidate.decision = "accepted"
    candidate.rejection_reason = None
    await session.commit()
    await session.refresh(candidate)
    return serialize_content_candidate(candidate)


@router.post("/content-pipeline/candidates/{candidate_id}/reject", response_model=AdminContentCandidateOut)
async def reject_admin_content_candidate(candidate_id: str, payload: AdminCandidateRejectPayload, session: SessionDep) -> AdminContentCandidateOut:
    candidate = await session.get(ContentCandidate, candidate_id)
    if candidate is None:
        raise AppError("CONTENT_CANDIDATE_NOT_FOUND", "Content candidate not found", 404)
    active_job = await session.scalar(
        select(ArticleGenerationJob.id).where(
            ArticleGenerationJob.candidate_id == candidate.id,
            ArticleGenerationJob.status.in_(("pending", "running")),
        )
    )
    if active_job is not None:
        raise AppError("CONTENT_CANDIDATE_GENERATING", "Candidates cannot be rejected while generation is running", 409)

    generated_articles = (
        await session.execute(
            select(Article)
            .join(ArticleGenerationJob, ArticleGenerationJob.generated_article_id == Article.id)
            .options(selectinload(Article.translations))
            .where(ArticleGenerationJob.candidate_id == candidate.id)
        )
    ).scalars().unique().all()
    now = datetime.now(UTC)
    for article in generated_articles:
        article.status = "archived"
        article.deleted_at = article.deleted_at or now
        for translation in article.translations:
            translation.translation_status = "draft"
    candidate.decision = "rejected"
    candidate.rejection_reason = payload.reason or "Rejected by admin"
    await session.commit()
    await session.refresh(candidate)
    return serialize_content_candidate(candidate)


@router.post("/content-pipeline/candidates/{candidate_id}/generate", response_model=AdminCandidateGenerateOut, status_code=202)
async def generate_admin_content_candidate(
    candidate_id: str,
    background_tasks: BackgroundTasks,
    session: SessionDep,
    admin: User = Depends(current_admin_user),
) -> AdminCandidateGenerateOut:
    job, candidate, should_start = await queue_article_generation(session, candidate_id)
    if should_start:
        background_tasks.add_task(run_queued_article_generation, job.id, candidate.id, admin.id)
    return AdminCandidateGenerateOut(
        job=serialize_article_generation_job(job),
        candidate=serialize_content_candidate(candidate),
        article_id=job.generated_article_id,
        article_status="queued" if job.status in {"pending", "running"} else job.status,
    )


@router.get("/content-pipeline/generation-jobs", response_model=list[AdminArticleGenerationJobOut])
async def admin_content_pipeline_generation_jobs(session: SessionDep) -> list[AdminArticleGenerationJobOut]:
    jobs = (
        await session.execute(
            select(ArticleGenerationJob)
            .options(selectinload(ArticleGenerationJob.mistral_logs))
            .order_by(ArticleGenerationJob.created_at.desc())
            .limit(50)
        )
    ).scalars().all()
    return [serialize_article_generation_job(job, sorted(job.mistral_logs, key=lambda item: item.created_at)) for job in jobs]


@router.get("/content-pipeline/generation-jobs/{job_id}", response_model=AdminArticleGenerationJobOut)
async def admin_content_pipeline_generation_job(job_id: str, session: SessionDep) -> AdminArticleGenerationJobOut:
    job = await session.scalar(
        select(ArticleGenerationJob)
        .options(selectinload(ArticleGenerationJob.mistral_logs))
        .where(ArticleGenerationJob.id == job_id)
    )
    if job is None:
        raise AppError("ARTICLE_GENERATION_JOB_NOT_FOUND", "Article generation job not found", 404)
    return serialize_article_generation_job(job, sorted(job.mistral_logs, key=lambda item: item.created_at))


@router.get("/ai/sources", response_model=list[AdminAiSourceOut])
async def admin_ai_sources(session: SessionDep) -> list[AdminAiSourceOut]:
    rows = (await session.execute(select(AiSource).order_by(AiSource.created_at.desc()))).scalars().all()
    return [serialize_ai_source(row) for row in rows]


@router.post("/ai/sources", response_model=AdminAiSourceOut, status_code=201)
async def create_admin_ai_source(payload: AdminAiSourcePayload, session: SessionDep) -> AdminAiSourceOut:
    source = AiSource(
        name=payload.name,
        base_url=str(payload.base_url),
        rss_url=str(payload.rss_url) if payload.rss_url else None,
        source_type=payload.source_type,
        is_active=payload.is_active,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)
    return serialize_ai_source(source)


@router.put("/ai/sources/{source_id}", response_model=AdminAiSourceOut)
async def update_admin_ai_source(source_id: str, payload: AdminAiSourcePayload, session: SessionDep) -> AdminAiSourceOut:
    source = await session.get(AiSource, source_id)
    if source is None:
        raise AppError("AI_SOURCE_NOT_FOUND", "AI source not found", 404)
    source.name = payload.name
    source.base_url = str(payload.base_url)
    source.rss_url = str(payload.rss_url) if payload.rss_url else None
    source.source_type = payload.source_type
    source.is_active = payload.is_active
    await session.commit()
    await session.refresh(source)
    return serialize_ai_source(source)


@router.delete("/ai/sources/{source_id}")
async def delete_admin_ai_source(source_id: str, session: SessionDep) -> dict:
    source = await session.get(AiSource, source_id)
    if source is None:
        raise AppError("AI_SOURCE_NOT_FOUND", "AI source not found", 404)
    await session.delete(source)
    await session.commit()
    return {"ok": True}


@router.get("/ai/jobs", response_model=list[AdminAiJobOut])
async def admin_ai_jobs(session: SessionDep) -> list[AdminAiJobOut]:
    rows = (await session.execute(select(AiIngestJob).order_by(AiIngestJob.created_at.desc()).limit(50))).scalars().all()
    return [await serialize_ai_job(row, session) for row in rows]


@router.get("/ai/jobs/{job_id}", response_model=AdminAiJobDetailOut)
async def admin_ai_job_detail(job_id: str, session: SessionDep) -> AdminAiJobDetailOut:
    job = await session.get(AiIngestJob, job_id)
    if job is None:
        raise AppError("AI_JOB_NOT_FOUND", "AI job not found", 404)
    return await serialize_ai_job(job, session, include_candidates=True)


@router.post("/ai/jobs/run-now", response_model=AdminAiJobDetailOut)
async def run_admin_ai_job(session: SessionDep) -> AdminAiJobDetailOut:
    job = await run_ai_ingest(session)
    return await serialize_ai_job(job, session, include_candidates=True)


@router.post("/ai/candidates/{candidate_id}/approve")
async def approve_admin_ai_candidate(candidate_id: str, session: SessionDep, admin: User = Depends(current_admin_user)) -> dict:
    candidate = await session.get(AiArticleCandidate, candidate_id)
    if candidate is None:
        raise AppError("AI_CANDIDATE_NOT_FOUND", "AI candidate not found", 404)
    if candidate.decision == "rejected":
        raise AppError("AI_CANDIDATE_REJECTED", "Rejected candidates cannot be approved", 409)
    article = await approve_candidate_as_article(session, candidate, admin)
    await session.commit()
    return {"ok": True, "article_id": article.id, "status": article.status}


@router.post("/ai/candidates/{candidate_id}/reject")
async def reject_admin_ai_candidate(candidate_id: str, payload: AdminAiRejectPayload, session: SessionDep) -> dict:
    candidate = await session.get(AiArticleCandidate, candidate_id)
    if candidate is None:
        raise AppError("AI_CANDIDATE_NOT_FOUND", "AI candidate not found", 404)
    if candidate.decision == "accepted":
        raise AppError("AI_CANDIDATE_ACCEPTED", "Accepted candidates cannot be rejected", 409)
    candidate.decision = "rejected"
    candidate.rejection_reason = payload.reason or "Rejected by admin"
    await session.commit()
    return {"ok": True}


def build_admin_articles_query(
    q: str | None = None,
    status: str | None = None,
    topic: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    is_featured: bool | None = None,
    show_ads: bool | None = None,
) -> Select[tuple[Article]]:
    stmt = (
        select(Article)
        .options(selectinload(Article.author), selectinload(Article.translations))
        .where(Article.deleted_at.is_(None))
        .order_by(Article.created_at.desc(), Article.id.desc())
    )
    if status:
        stmt = stmt.where(Article.status == status)
    if is_featured is not None:
        stmt = stmt.where(Article.is_featured.is_(is_featured))
    if show_ads is not None:
        stmt = stmt.where(Article.show_ads.is_(show_ads))
    keyword = q.strip() if q else ""
    if keyword:
        pattern = f"%{keyword}%"
        stmt = stmt.where(
            Article.id.in_(
                select(ArticleTranslation.article_id).where(
                    or_(
                        ArticleTranslation.title.ilike(pattern),
                        ArticleTranslation.slug.ilike(pattern),
                        ArticleTranslation.excerpt.ilike(pattern),
                        ArticleTranslation.content_text.ilike(pattern),
                    )
                )
            )
        )
    if topic:
        stmt = stmt.where(
            Article.id.in_(
                select(ArticleTopic.article_id)
                .join(Topic, Topic.id == ArticleTopic.topic_id)
                .where(Topic.slug == topic)
            )
        )
    local_timezone = ZoneInfo(get_settings().content_pipeline_timezone)
    if created_from:
        start_at = datetime.combine(created_from, time.min, tzinfo=local_timezone).astimezone(UTC)
        stmt = stmt.where(Article.created_at >= start_at)
    if created_to:
        exclusive_end = datetime.combine(created_to + timedelta(days=1), time.min, tzinfo=local_timezone).astimezone(UTC)
        stmt = stmt.where(Article.created_at < exclusive_end)
    return stmt


@router.get("/articles")
async def admin_articles(
    session: SessionDep,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    topic: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    is_featured: bool | None = None,
    show_ads: bool | None = None,
) -> dict:
    if created_from and created_to and created_from > created_to:
        raise AppError("INVALID_ARTICLE_DATE_RANGE", "created_from must not be after created_to", 422)
    stmt = build_admin_articles_query(q, status, topic, created_from, created_to, is_featured, show_ads)
    total = await session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (await session.execute(stmt.offset((page - 1) * page_size).limit(page_size))).scalars().unique().all()
    topics_by_article: dict[str, list[dict]] = {row.id: [] for row in rows}
    if rows:
        topic_rows = (
            await session.execute(
                select(ArticleTopic.article_id, Topic.id, Topic.slug, Topic.name_zh, Topic.name_en)
                .join(Topic, Topic.id == ArticleTopic.topic_id)
                .where(ArticleTopic.article_id.in_([row.id for row in rows]))
                .order_by(ArticleTopic.is_primary.desc(), Topic.name_zh)
            )
        ).all()
        for article_id, topic_id, slug, name_zh, name_en in topic_rows:
            topics_by_article[article_id].append(
                {"id": topic_id, "slug": slug, "name_zh": name_zh, "name_en": name_en}
            )
    items = []
    for row in rows:
        item = (await serialize_article_item(row)).model_dump()
        item["topics"] = topics_by_article[row.id]
        items.append(item)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/articles/{article_id}")
async def admin_article_detail(article_id: str, session: SessionDep) -> dict:
    article = await session.scalar(
        select(Article)
        .options(selectinload(Article.author), selectinload(Article.translations))
        .where(Article.id == article_id, Article.deleted_at.is_(None))
    )
    if article is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    topics = (
        await session.execute(select(ArticleTopic).where(ArticleTopic.article_id == article.id).order_by(ArticleTopic.is_primary.desc()))
    ).scalars().all()
    return {
        "id": article.id,
        "author_id": article.author_id,
        "status": article.status,
        "is_featured": article.is_featured,
        "show_ads": article.show_ads,
        "hero_image_url": article.hero_image_url,
        "thumbnail_url": article.thumbnail_url,
        "og_image_url": article.og_image_url,
        "topic_ids": [topic.topic_id for topic in topics],
        "translations": [
            {
                "id": translation.id,
                "locale": translation.locale,
                "title": translation.title,
                "slug": translation.slug,
                "excerpt": translation.excerpt,
                "content_html": translation.content_html,
                "content_text": translation.content_text,
                "seo_title": translation.seo_title,
                "seo_description": translation.seo_description,
                "translation_status": translation.translation_status,
            }
            for translation in article.translations
        ],
    }


@router.post("/articles", status_code=201)
async def create_admin_article(payload: AdminArticlePayload, session: SessionDep, admin: User = Depends(current_admin_user)) -> dict:
    author = await session.get(Author, payload.author_id) if payload.author_id else await get_default_author(session)
    article = Article(author_id=author.id, created_by=admin.id, updated_by=admin.id)
    session.add(article)
    await session.flush()
    await apply_article_payload(article, payload, session, admin)
    await commit_article_changes(session)
    await session.refresh(article)
    return {"id": article.id, "status": article.status}


@router.put("/articles/{article_id}")
async def update_admin_article(article_id: str, payload: AdminArticlePayload, session: SessionDep, admin: User = Depends(current_admin_user)) -> dict:
    article = await session.scalar(
        select(Article).options(selectinload(Article.translations)).where(Article.id == article_id, Article.deleted_at.is_(None))
    )
    if article is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    await apply_article_payload(article, payload, session, admin)
    await commit_article_changes(session)
    return {"id": article.id, "status": article.status}


@router.delete("/articles/{article_id}")
async def delete_admin_article(article_id: str, session: SessionDep) -> dict:
    article = await session.scalar(
        select(Article)
        .options(selectinload(Article.translations))
        .where(Article.id == article_id, Article.deleted_at.is_(None))
    )
    if article is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    for translation in article.translations:
        translation.slug = released_article_slug(translation.slug, translation.id)
    article.deleted_at = datetime.now(UTC)
    article.status = "archived"
    await session.commit()
    return {"ok": True}


@router.post("/articles/{article_id}/publish")
async def publish_admin_article(article_id: str, session: SessionDep) -> dict:
    article = await session.scalar(
        select(Article).options(selectinload(Article.translations)).where(Article.id == article_id, Article.deleted_at.is_(None))
    )
    if article is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    article.status = "published"
    article.published_at = article.published_at or datetime.now(UTC)
    article.first_published_at = article.first_published_at or article.published_at
    for translation in article.translations:
        translation.translation_status = "published"
    await session.commit()
    return {"ok": True}


@router.post("/articles/{article_id}/archive")
async def archive_admin_article(article_id: str, session: SessionDep) -> dict:
    article = await session.scalar(
        select(Article).options(selectinload(Article.translations)).where(Article.id == article_id, Article.deleted_at.is_(None))
    )
    if article is None:
        raise AppError("ARTICLE_NOT_FOUND", "Article not found", 404)
    article.status = "archived"
    for translation in article.translations:
        translation.translation_status = "draft"
    await session.commit()
    return {"ok": True}


@router.get("/topics")
async def admin_topics(session: SessionDep) -> list[dict]:
    rows = (await session.execute(select(Topic).order_by(Topic.name_en))).scalars().all()
    return [{"id": row.id, "slug": row.slug, "name_zh": row.name_zh, "name_en": row.name_en} for row in rows]


@router.get("/tags")
async def admin_tags(session: SessionDep) -> list[dict]:
    return await admin_topics(session)


@router.get("/authors")
async def admin_authors(session: SessionDep) -> list[dict]:
    rows = (await session.execute(select(Author).order_by(Author.display_name))).scalars().all()
    return [{"id": row.id, "slug": row.slug, "display_name": row.display_name} for row in rows]


@router.get("/users")
async def admin_users(session: SessionDep, q: str | None = None) -> dict:
    stmt = select(User).where(User.deleted_at.is_(None)).order_by(User.created_at.desc())
    if q:
        stmt = stmt.where(or_(User.email.ilike(f"%{q}%"), User.display_name.ilike(f"%{q}%")))
    rows = (await session.execute(stmt.limit(100))).scalars().all()
    return {
        "items": [
            {
                "id": row.id,
                "email": row.email,
                "display_name": row.display_name,
                "role": row.role,
                "email_verified": row.email_verified,
                "is_active": row.is_active,
                "created_at": row.created_at,
                "last_login_at": row.last_login_at,
            }
            for row in rows
        ]
    }


@router.get("/users/{user_id}")
async def admin_user_detail(user_id: str, session: SessionDep) -> dict:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "role": user.role,
        "email_verified": user.email_verified,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
    }


@router.put("/users/{user_id}")
async def update_admin_user(user_id: str, payload: AdminUserUpdate, session: SessionDep) -> dict:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(user, key, value)
    await session.commit()
    return {"ok": True}


@router.delete("/users/{user_id}")
async def delete_admin_user(user_id: str, session: SessionDep, admin: User = Depends(current_admin_user)) -> dict:
    user = await session.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise AppError("USER_NOT_FOUND", "User not found", 404)
    if user.id == admin.id:
        raise AppError("ADMIN_SELF_DELETE_NOT_ALLOWED", "Administrators cannot delete their own account", 409)
    await session.execute(delete(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id))
    user.email = f"deleted-{user.id}@users.invalid"
    user.is_active = False
    user.deleted_at = datetime.now(UTC)
    await session.commit()
    return {"ok": True}


@router.get("/ads", response_model=list[AdminAdOut])
async def admin_ads(session: SessionDep) -> list[AdminAdOut]:
    rows = (await session.execute(select(Ad).order_by(Ad.updated_at.desc()))).scalars().all()
    return [serialize_ad(row) for row in rows]


@router.post("/ads", response_model=AdminAdOut, status_code=201)
async def create_admin_ad(payload: AdminAdPayload, session: SessionDep) -> AdminAdOut:
    ad = Ad(
        name=payload.name,
        title=payload.name,
        image_url=payload.image_url,
        target_url=str(payload.target_url),
        alt_text=payload.alt_text,
        placement=payload.placement,
        placement_key=payload.placement,
        is_active=payload.status == "active",
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        weight=payload.weight,
        open_in_new_tab=True,
    )
    session.add(ad)
    await session.commit()
    await session.refresh(ad)
    return serialize_ad(ad)


@router.get("/ads/{ad_id}", response_model=AdminAdOut)
async def admin_ad_detail(ad_id: str, session: SessionDep) -> AdminAdOut:
    ad = await session.get(Ad, ad_id)
    if ad is None:
        raise AppError("AD_NOT_FOUND", "Ad not found", 404)
    return serialize_ad(ad)


@router.put("/ads/{ad_id}", response_model=AdminAdOut)
async def update_admin_ad(ad_id: str, payload: AdminAdPayload, session: SessionDep) -> AdminAdOut:
    ad = await session.get(Ad, ad_id)
    if ad is None:
        raise AppError("AD_NOT_FOUND", "Ad not found", 404)
    ad.name = payload.name
    ad.title = payload.name
    ad.image_url = payload.image_url
    ad.target_url = str(payload.target_url)
    ad.alt_text = payload.alt_text
    ad.placement = payload.placement
    ad.placement_key = payload.placement
    ad.is_active = payload.status == "active"
    ad.starts_at = payload.starts_at
    ad.ends_at = payload.ends_at
    ad.weight = payload.weight
    await session.commit()
    await session.refresh(ad)
    return serialize_ad(ad)


@router.delete("/ads/{ad_id}")
async def delete_admin_ad(ad_id: str, session: SessionDep) -> dict:
    ad = await session.get(Ad, ad_id)
    if ad is None:
        raise AppError("AD_NOT_FOUND", "Ad not found", 404)
    await session.delete(ad)
    await session.commit()
    return {"ok": True}


@router.post("/uploads/image")
async def upload_image(file: UploadFile = File(...)) -> dict:
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise AppError("INVALID_FILE_TYPE", "Only jpg, png, webp, and gif images are allowed", 400)
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise AppError("FILE_TOO_LARGE", "Image must be 5MB or smaller", 400)
    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    extension = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{uuid4().hex}{extension}"
    path = upload_dir / filename
    path.write_bytes(data)
    return {"url": f"/uploads/{filename}", "filename": filename, "content_type": file.content_type, "size": len(data)}


@router.get("/comments")
async def admin_comments(session: SessionDep, status: str | None = None) -> list[dict]:
    stmt = select(Comment).order_by(Comment.created_at.desc())
    if status:
        stmt = stmt.where(Comment.status == status)
    rows = (await session.execute(stmt.limit(100))).scalars().all()
    return [
        {
            "id": row.id,
            "article_id": row.article_id,
            "author_name": row.author_name,
            "status": row.status,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.patch("/comments/{comment_id}/status")
async def moderate_comment(comment_id: str, payload: dict, session: SessionDep) -> dict:
    comment = await session.get(Comment, comment_id)
    if comment is None:
        raise AppError("COMMENT_NOT_FOUND", "Comment not found", 404)
    comment.status = payload["status"]
    await session.commit()
    return {"ok": True}
