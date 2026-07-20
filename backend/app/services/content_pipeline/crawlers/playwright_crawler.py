from app.core.config import get_settings
from app.models import SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawlResult


async def crawl_playwright(source: SourceWhitelist, candidate_limit: int | None = None) -> CrawlResult:
    settings = get_settings()
    if not settings.content_pipeline_playwright_enabled:
        return CrawlResult(
            fallback_used={
                "method": "playwright",
                "status": "skipped",
                "message": "Playwright crawler disabled by CONTENT_PIPELINE_PLAYWRIGHT_ENABLED",
            }
        )
    return CrawlResult(
        fallback_used={
            "method": "playwright",
            "status": "unavailable",
            "message": "Playwright runtime is not installed in the backend image",
        },
        error_message="Playwright runtime is not installed",
    )
