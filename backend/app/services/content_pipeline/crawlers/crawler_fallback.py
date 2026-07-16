from app.models import SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawlResult, normalize_domain
from app.services.content_pipeline.crawlers.http_crawler import fetch_text
from app.services.content_pipeline.crawlers.yahoo_autos_crawler import crawl_yahoo_autos
from app.services.content_pipeline.parsers.html_parser import parse_evoasis_candidates, parse_html_candidates


async def crawl_static_html(source: SourceWhitelist) -> CrawlResult:
    if normalize_domain(source.domain) == "autos.yahoo.com.tw":
        return await crawl_yahoo_autos(source)
    target_url = source.list_url or source.homepage_url
    if not target_url:
        return CrawlResult(fallback_used={"method": "html", "status": "skipped", "message": "No list or homepage URL configured"})
    try:
        raw_html, final_url = await fetch_text(target_url)
    except Exception as exc:
        return CrawlResult(
            fallback_used={"method": "html", "status": "failed", "message": str(exc)[:500]},
            error_message=str(exc)[:1000],
        )
    if normalize_domain(source.domain) == "evoasis.com.tw":
        candidates = parse_evoasis_candidates(raw_html, final_url, source.domain, source.max_candidates_per_run)
    else:
        candidates = parse_html_candidates(raw_html, final_url, source.domain, source.max_candidates_per_run)
    return CrawlResult(
        candidates=candidates,
        fallback_used={"method": "html", "status": "success" if candidates else "empty", "url": final_url},
    )
