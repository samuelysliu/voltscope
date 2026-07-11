from app.models import SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawlResult
from app.services.content_pipeline.crawlers.http_crawler import fetch_text
from app.services.content_pipeline.parsers.rss_parser import parse_rss_candidates


async def crawl_rss(source: SourceWhitelist) -> CrawlResult:
    if not source.rss_url:
        return CrawlResult(fallback_used={"method": "rss", "status": "skipped", "message": "No RSS URL configured"})
    try:
        raw_xml, final_url = await fetch_text(source.rss_url)
    except Exception as exc:
        return CrawlResult(
            fallback_used={"method": "rss", "status": "failed", "message": str(exc)[:500]},
            error_message=str(exc)[:1000],
        )
    candidates = parse_rss_candidates(raw_xml, final_url, source.domain, source.max_candidates_per_run)
    return CrawlResult(
        candidates=candidates,
        fallback_used={"method": "rss", "status": "success" if candidates else "empty", "url": final_url},
    )
