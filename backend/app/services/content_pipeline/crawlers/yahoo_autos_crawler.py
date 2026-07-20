from app.models import SourceWhitelist
from app.services.content_pipeline.crawlers.base import CrawlResult, is_allowed_url
from app.services.content_pipeline.crawlers.http_crawler import fetch_text
from app.services.content_pipeline.parsers.html_parser import parse_yahoo_autos_candidates


async def crawl_yahoo_autos(source: SourceWhitelist, candidate_limit: int | None = None) -> CrawlResult:
    targets = [
        (source.list_url, "ev_topic", False),
        (source.homepage_url, "homepage_ev_filter", True),
    ]
    attempts: list[dict] = []
    errors: list[str] = []
    visited: set[str] = set()

    for target_url, strategy, require_ev_keyword in targets:
        if not target_url or target_url in visited:
            continue
        visited.add(target_url)
        try:
            raw_html, final_url = await fetch_text(target_url)
            if not is_allowed_url(final_url, source.domain):
                raise ValueError(f"Yahoo redirected outside the approved domain: {final_url}")
            candidates = parse_yahoo_autos_candidates(
                raw_html,
                final_url,
                source.domain,
                candidate_limit or source.max_candidates_per_run,
                require_ev_keyword=require_ev_keyword,
            )
            attempts.append(
                {
                    "strategy": strategy,
                    "status": "success" if candidates else "empty",
                    "url": final_url,
                }
            )
            if candidates:
                return CrawlResult(
                    candidates=candidates,
                    fallback_used={
                        "method": "html",
                        "status": "success",
                        "strategy": strategy,
                        "attempts": attempts,
                    },
                )
        except Exception as exc:
            message = str(exc)[:500]
            errors.append(message)
            attempts.append({"strategy": strategy, "status": "failed", "url": target_url, "message": message})

    error_message = "; ".join(errors)[:1000] if errors else "No Yahoo Autos EV candidates found"
    return CrawlResult(
        fallback_used={"method": "html", "status": "failed", "strategy": "yahoo_autos", "attempts": attempts},
        error_message=error_message,
    )
