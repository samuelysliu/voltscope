from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import AsyncSessionLocal
from app.models import (
    Article,
    ArticleGenerationJob,
    ArticleTranslation,
    Author,
    ContentCandidate,
    MistralGenerationLog,
    SourceWhitelist,
    User,
)
from app.services.content_pipeline.ai.mistral_client import MistralClient, MistralJsonResult
from app.services.content_pipeline.ai.prompts import article_generation_messages, article_revision_messages, factual_notes_messages
from app.services.content_pipeline.quality_gates import run_quality_gates
from app.services.content_pipeline.source_material import fetch_candidate_source_material
from app.services.article_classification import classify_generated_article
from app.services.sanitize import sanitize_html


logger = logging.getLogger(__name__)


@dataclass
class ArticleGenerationResult:
    job: ArticleGenerationJob
    candidate: ContentCandidate
    article: Article


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:180] or "content-pipeline-article"


async def unique_slug(session: AsyncSession, base: str, locale: str) -> str:
    candidate = slugify(base)
    for index in range(50):
        slug = candidate if index == 0 else f"{candidate}-{index + 1}"
        exists = await session.scalar(select(ArticleTranslation.id).where(ArticleTranslation.locale == locale, ArticleTranslation.slug == slug))
        if exists is None:
            return slug
    return f"{candidate}-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"


async def get_default_author(session: AsyncSession) -> Author:
    author = await session.scalar(select(Author).where(Author.slug == "editorial-team"))
    if author is None:
        author = Author(slug="editorial-team", display_name="Editorial Team")
        session.add(author)
        await session.flush()
    return author


def normalize_article_payload(payload: dict) -> dict:
    required = ("title", "slug", "excerpt", "html", "text", "seo_title", "seo_description")
    if not isinstance(payload, dict):
        raise AppError("AI_ARTICLE_INVALID", "AI returned an invalid article object", 502)
    missing = [key for key in required if not isinstance(payload.get(key), str) or not payload[key].strip()]
    if missing:
        raise AppError(
            "AI_ARTICLE_INVALID",
            "AI returned an incomplete article",
            502,
            {"missing_fields": missing},
        )
    normalized = {key: payload[key].strip() for key in required}
    normalized["title"] = normalized["title"][:255]
    normalized["excerpt"] = normalized["excerpt"][:1000]
    normalized["seo_title"] = normalized.get("seo_title", normalized["title"])[:255]
    normalized["seo_description"] = normalized.get("seo_description", normalized["excerpt"])[:320]
    normalized["html"] = sanitize_html(normalized["html"])
    html_with_breaks = re.sub(r"</(?:p|h[1-6]|li)>", "\n", normalized["html"], flags=re.IGNORECASE)
    html_text = " ".join(unescape(re.sub(r"<[^>]+>", " ", html_with_breaks)).split())
    provided_text = " ".join(normalized.get("text", "").split())
    normalized["text"] = html_text if len(html_text) > len(provided_text) * 1.2 else provided_text
    return normalized


async def add_generation_log(
    session: AsyncSession,
    job: ArticleGenerationJob,
    purpose: str,
    status: str,
    model_name: str,
    latency_ms: int | None = None,
    input_token_count: int | None = None,
    output_token_count: int | None = None,
    error_message: str | None = None,
) -> None:
    settings = get_settings()
    session.add(
        MistralGenerationLog(
            generation_job_id=job.id,
            purpose=purpose,
            model_name=model_name,
            prompt_version=settings.mistral_prompt_version,
            input_token_count=input_token_count,
            output_token_count=output_token_count,
            latency_ms=latency_ms,
            status=status,
            error_message=error_message[:4000] if error_message else None,
        )
    )


async def generate_json(
    session: AsyncSession,
    job: ArticleGenerationJob,
    client: MistralClient,
    purpose: str,
    messages: list[dict[str, str]],
) -> dict:
    if not client.is_configured:
        raise AppError("AI_PROVIDER_NOT_CONFIGURED", "Mistral API key is not configured", 503)
    try:
        result: MistralJsonResult = await client.complete_json(messages, purpose)
        await add_generation_log(
            session,
            job,
            purpose,
            "success",
            result.model_name,
            latency_ms=result.latency_ms,
            input_token_count=result.input_tokens,
            output_token_count=result.output_tokens,
        )
        return result.data
    except Exception as exc:
        await add_generation_log(session, job, purpose, "failed", client.model_name, error_message=str(exc))
        raise AppError(
            "AI_GENERATION_FAILED",
            "AI article generation failed",
            502,
            {"purpose": purpose, "reason": str(exc)[:500]},
        ) from exc


async def queue_article_generation(
    session: AsyncSession,
    candidate_id: str,
) -> tuple[ArticleGenerationJob, ContentCandidate, bool]:
    candidate = await session.scalar(
        select(ContentCandidate).options(selectinload(ContentCandidate.source)).where(ContentCandidate.id == candidate_id)
    )
    if candidate is None:
        raise AppError("CONTENT_CANDIDATE_NOT_FOUND", "Content candidate not found", 404)
    if candidate.decision == "rejected":
        raise AppError("CONTENT_CANDIDATE_REJECTED", "Rejected candidates cannot be generated", 409)
    if candidate.decision in {"generated", "published"}:
        raise AppError("CONTENT_CANDIDATE_ALREADY_GENERATED", "Candidate has already generated an article", 409)

    settings = get_settings()
    if not MistralClient().is_configured:
        raise AppError("AI_PROVIDER_NOT_CONFIGURED", "Mistral API key is not configured", 503)

    active_job = await session.scalar(
        select(ArticleGenerationJob)
        .where(
            ArticleGenerationJob.candidate_id == candidate.id,
            ArticleGenerationJob.status.in_(("pending", "running")),
        )
        .order_by(ArticleGenerationJob.created_at.desc())
    )
    if active_job is not None:
        return active_job, candidate, False

    now = datetime.now(UTC)
    job = ArticleGenerationJob(
        candidate_id=candidate.id,
        status="pending",
        provider="mistral",
        model_name=settings.mistral_model,
        prompt_version=settings.mistral_prompt_version,
        created_at=now,
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job, candidate, True


async def run_queued_article_generation(job_id: str, candidate_id: str, admin_id: str) -> None:
    async with AsyncSessionLocal() as session:
        admin = await session.get(User, admin_id)
        if admin is None:
            job = await session.get(ArticleGenerationJob, job_id)
            if job is not None:
                job.status = "failed"
                job.error_message = "Admin user no longer exists"
                job.finished_at = datetime.now(UTC)
                await session.commit()
            return
        try:
            await generate_article_from_candidate(session, candidate_id, admin, generation_job_id=job_id)
        except Exception:
            logger.exception("Queued article generation failed", extra={"job_id": job_id, "candidate_id": candidate_id})


async def recover_interrupted_generation_jobs() -> int:
    async with AsyncSessionLocal() as session:
        jobs = (
            await session.execute(
                select(ArticleGenerationJob).where(ArticleGenerationJob.status.in_(("pending", "running")))
            )
        ).scalars().all()
        if not jobs:
            return 0
        now = datetime.now(UTC)
        for job in jobs:
            job.status = "failed"
            job.finished_at = now
            job.error_message = "Article generation was interrupted by a service restart"
            candidate = await session.get(ContentCandidate, job.candidate_id)
            if candidate is not None and candidate.decision not in {"generated", "published", "rejected"}:
                candidate.decision = "failed"
                candidate.rejection_reason = "generation_interrupted"
        await session.commit()
        return len(jobs)


async def generate_article_from_candidate(
    session: AsyncSession,
    candidate_id: str,
    admin: User,
    generation_job_id: str | None = None,
) -> ArticleGenerationResult:
    candidate = await session.scalar(
        select(ContentCandidate).options(selectinload(ContentCandidate.source)).where(ContentCandidate.id == candidate_id)
    )
    if candidate is None:
        raise AppError("CONTENT_CANDIDATE_NOT_FOUND", "Content candidate not found", 404)
    if candidate.decision == "rejected":
        raise AppError("CONTENT_CANDIDATE_REJECTED", "Rejected candidates cannot be generated", 409)
    if candidate.decision in {"generated", "published"}:
        raise AppError("CONTENT_CANDIDATE_ALREADY_GENERATED", "Candidate has already generated an article", 409)

    settings = get_settings()
    client = MistralClient()
    started = datetime.now(UTC)
    if generation_job_id:
        job = await session.get(ArticleGenerationJob, generation_job_id)
        if job is None or job.candidate_id != candidate.id:
            raise AppError("ARTICLE_GENERATION_JOB_NOT_FOUND", "Article generation job not found", 404)
        job.status = "running"
        job.started_at = started
        job.finished_at = None
        job.error_message = None
    else:
        job = ArticleGenerationJob(
            candidate_id=candidate.id,
            status="running",
            provider="mistral",
            model_name=settings.mistral_model,
            prompt_version=settings.mistral_prompt_version,
            started_at=started,
            created_at=started,
        )
        session.add(job)
    await session.flush()
    await session.commit()

    try:
        if not client.is_configured:
            raise AppError("AI_PROVIDER_NOT_CONFIGURED", "Mistral API key is not configured", 503)
        source_material = await fetch_candidate_source_material(candidate)
        candidate.raw_text_excerpt = source_material[:1000]
        notes = await generate_json(
            session,
            job,
            client,
            "factual_notes",
            factual_notes_messages(candidate, source_material),
        )
        candidate.factual_notes = notes
        if notes.get("should_publish") is False:
            raise AppError(
                "SOURCE_FACTS_INSUFFICIENT",
                "AI could not establish enough verified facts from the source article",
                422,
                {"reason": notes.get("reason")},
            )
        zh_payload = normalize_article_payload(
            await generate_json(
                session,
                job,
                client,
                "zh_generation",
                article_generation_messages(candidate, notes, "zh-TW", source_material),
            )
        )
        en_payload = normalize_article_payload(
            await generate_json(
                session,
                job,
                client,
                "en_generation",
                article_generation_messages(candidate, notes, "en", source_material),
            )
        )
        shared_revision_codes = {
            "generic_article_template_detected",
            "missing_source_attribution",
            "source_sentence_overlap_too_high",
        }
        zh_revision_codes = {
            "zh_article_short",
            "zh_title_contains_source_title",
            "zh_title_not_localized",
            *shared_revision_codes,
        }
        en_revision_codes = {"en_article_short", *shared_revision_codes}
        gate = run_quality_gates(candidate, zh_payload, en_payload)
        for _ in range(2):
            if gate["pass"]:
                break
            issue_codes = {item["code"] for item in gate["issues"] if item["severity"] == "critical"}
            revision_requested = False
            if issue_codes.intersection(zh_revision_codes):
                revision_requested = True
                zh_payload = normalize_article_payload(
                    await generate_json(
                        session,
                        job,
                        client,
                        "zh_revision",
                        article_revision_messages(candidate, notes, "zh-TW", zh_payload, sorted(issue_codes.intersection(zh_revision_codes))),
                    )
                )
            if issue_codes.intersection(en_revision_codes):
                revision_requested = True
                en_payload = normalize_article_payload(
                    await generate_json(
                        session,
                        job,
                        client,
                        "en_revision",
                        article_revision_messages(candidate, notes, "en", en_payload, sorted(issue_codes.intersection(en_revision_codes))),
                    )
                )
            gate = run_quality_gates(candidate, zh_payload, en_payload)
            if not revision_requested:
                break
        await add_generation_log(
            session,
            job,
            "quality_check",
            "success" if gate["pass"] else "failed",
            "deterministic-quality-gates",
            latency_ms=0,
            input_token_count=0,
            output_token_count=0,
            error_message=None if gate["pass"] else "Quality gate failed",
        )
        if not gate["pass"]:
            candidate.decision = "failed"
            candidate.rejection_reason = "failed_quality_gate"
            job.quality_gate_result = gate
            raise AppError("ARTICLE_GENERATION_QUALITY_GATE_FAILED", "Generated article failed quality gate", 422, gate)

        source = candidate.__dict__.get("source")
        should_publish = bool(
            settings.content_pipeline_auto_publish
            and isinstance(source, SourceWhitelist)
            and source.allow_auto_publish
            and not source.requires_review
        )
        status = "published" if should_publish else "draft"
        author = await get_default_author(session)
        now = datetime.now(UTC)
        article = Article(
            author_id=author.id,
            admin_author_id=admin.id,
            status=status,
            source_type="content_pipeline",
            primary_source_url=candidate.source_url,
            primary_source_name=source.name if isinstance(source, SourceWhitelist) else None,
            created_by=admin.id,
            updated_by=admin.id,
            published_at=now if status == "published" else None,
            first_published_at=now if status == "published" else None,
        )
        session.add(article)
        await session.flush()

        session.add(
            ArticleTranslation(
                article_id=article.id,
                locale="zh-TW",
                title=zh_payload["title"],
                slug=await unique_slug(session, zh_payload.get("slug") or zh_payload["title"], "zh-TW"),
                excerpt=zh_payload["excerpt"],
                content_json={"type": "doc", "source": "content_pipeline_mistral", "candidate_id": candidate.id},
                content_html=zh_payload["html"],
                content_text=zh_payload["text"],
                seo_title=zh_payload["seo_title"],
                seo_description=zh_payload["seo_description"],
                og_title=zh_payload["title"],
                og_description=zh_payload["excerpt"][:320],
                translation_status=status,
            )
        )
        session.add(
            ArticleTranslation(
                article_id=article.id,
                locale="en",
                title=en_payload["title"],
                slug=await unique_slug(session, en_payload.get("slug") or en_payload["title"], "en"),
                excerpt=en_payload["excerpt"],
                content_json={"type": "doc", "source": "content_pipeline_mistral", "candidate_id": candidate.id},
                content_html=en_payload["html"],
                content_text=en_payload["text"],
                seo_title=en_payload["seo_title"],
                seo_description=en_payload["seo_description"],
                og_title=en_payload["title"],
                og_description=en_payload["excerpt"][:320],
                translation_status=status,
            )
        )

        classification_text = " ".join(
            [
                candidate.source_title,
                candidate.source_excerpt or "",
                zh_payload["title"],
                zh_payload["excerpt"],
                zh_payload["text"],
                en_payload["title"],
                en_payload["excerpt"],
                en_payload["text"],
            ]
        )
        await classify_generated_article(session, article.id, classification_text)

        candidate.decision = "published" if status == "published" else "generated"
        candidate.rejection_reason = None
        job.status = "success"
        job.finished_at = datetime.now(UTC)
        job.generated_article_id = article.id
        job.quality_gate_result = gate
        await session.commit()
        await session.refresh(job)
        await session.refresh(candidate)
        await session.refresh(article)
        return ArticleGenerationResult(job=job, candidate=candidate, article=article)
    except AppError as exc:
        job.status = "failed"
        job.finished_at = datetime.now(UTC)
        job.error_message = exc.message
        await session.commit()
        raise
    except Exception as exc:
        job.status = "failed"
        job.finished_at = datetime.now(UTC)
        job.error_message = str(exc)[:4000]
        await session.commit()
        raise
