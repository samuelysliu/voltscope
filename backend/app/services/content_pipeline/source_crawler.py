from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import CrawlerRun, SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawledCandidate, CrawlResult
from app.services.content_pipeline.crawlers.crawler_fallback import crawl_static_html
from app.services.content_pipeline.crawlers.playwright_crawler import crawl_playwright
from app.services.content_pipeline.crawlers.rss_crawler import crawl_rss


@dataclass
class TestCrawlResult:
    source: SourceWhitelist
    run: CrawlerRun
    candidates: list[CrawledCandidate]


def _method_plan(source: SourceWhitelist) -> list[str]:
    if source.crawl_method == "rss":
        return ["rss", "html", "playwright"]
    if source.crawl_method == "html":
        return ["html", "rss", "playwright"]
    if source.crawl_method == "playwright":
        return ["playwright", "html", "rss"]
    if source.crawl_method == "hybrid":
        return ["rss", "html", "playwright"]
    if source.crawl_method == "api":
        return ["api", "rss", "html", "playwright"]
    return ["rss", "html", "playwright"]


async def _run_method(method: str, source: SourceWhitelist) -> CrawlResult:
    if method == "rss":
        return await crawl_rss(source)
    if method == "html":
        return await crawl_static_html(source)
    if method == "playwright":
        return await crawl_playwright(source)
    return CrawlResult(
        fallback_used={
            "method": "api",
            "status": "skipped",
            "message": "Structured API crawler is not configured for this source",
        }
    )


def _mark_source_success(source: SourceWhitelist, now: datetime) -> None:
    source.last_success_at = now
    source.consecutive_failures = 0
    source.health_status = "healthy" if source.enabled else "disabled"


def _mark_source_failure(source: SourceWhitelist, now: datetime) -> None:
    source.last_failure_at = now
    source.consecutive_failures = (source.consecutive_failures or 0) + 1
    if not source.enabled:
        source.health_status = "disabled"
    else:
        source.health_status = "degraded" if source.consecutive_failures >= 3 else "failed"


async def test_crawl_source(session: AsyncSession, source_id: str) -> TestCrawlResult:
    source = await session.get(SourceWhitelist, source_id)
    if source is None:
        raise AppError("CONTENT_SOURCE_NOT_FOUND", "Content source not found", 404)

    now = datetime.now(UTC)
    run = CrawlerRun(source_id=source.id, job_type="source_test", status="running", started_at=now, created_at=now)
    session.add(run)
    await session.flush()

    candidates: list[CrawledCandidate] = []
    attempts: list[dict] = []
    error_message: str | None = None

    try:
        if not source.enabled:
            error_message = "Source is disabled"
            attempts.append({"method": "source", "status": "skipped", "message": error_message})
        else:
            seen_urls: set[str] = set()
            for method in _method_plan(source):
                result = await _run_method(method, source)
                attempts.append(result.fallback_used)
                if result.error_message and not error_message:
                    error_message = result.error_message
                for candidate in result.candidates:
                    if candidate.source_url in seen_urls:
                        continue
                    seen_urls.add(candidate.source_url)
                    candidates.append(candidate)
                    if len(candidates) >= source.max_candidates_per_run:
                        break
                if candidates:
                    break

        finished = datetime.now(UTC)
        run.finished_at = finished
        run.candidates_found = len(candidates)
        run.candidates_accepted = len(candidates)
        run.fallback_used = {"attempts": attempts}
        if candidates:
            primary_method = attempts[0].get("method") if attempts else None
            successful_method = attempts[-1].get("method") if attempts else None
            run.status = "success" if primary_method == successful_method else "partial_success"
            run.error_message = None
            _mark_source_success(source, finished)
        else:
            run.status = "failed"
            run.error_message = error_message or "No candidates found"
            _mark_source_failure(source, finished)
        await session.commit()
        await session.refresh(run)
        await session.refresh(source)
        return TestCrawlResult(source=source, run=run, candidates=candidates)
    except Exception as exc:
        finished = datetime.now(UTC)
        run.status = "failed"
        run.finished_at = finished
        run.error_message = str(exc)[:4000]
        run.fallback_used = {"attempts": attempts}
        _mark_source_failure(source, finished)
        await session.commit()
        raise
