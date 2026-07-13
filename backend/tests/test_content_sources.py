from types import SimpleNamespace
from typing import cast

import pytest

from app.models import SourceWhitelist
from app.services.content_pipeline.crawlers import yahoo_autos_crawler
from app.services.content_pipeline.parsers.html_parser import parse_yahoo_autos_candidates
from scripts.seed_content_sources import DEFAULT_SOURCES


def yahoo_source() -> SourceWhitelist:
    return cast(
        SourceWhitelist,
        SimpleNamespace(
            domain="autos.yahoo.com.tw",
            list_url="https://autos.yahoo.com.tw/car-topics/EV-and-Hybrid",
            homepage_url="https://autos.yahoo.com.tw",
            max_candidates_per_run=10,
        ),
    )


def test_source_catalog_expands_regional_and_international_coverage() -> None:
    names = {source["name"] for source in DEFAULT_SOURCES}
    yahoo = next(source for source in DEFAULT_SOURCES if source["name"] == "Yahoo Taiwan Autos EV")

    assert yahoo["list_url"] == "https://autos.yahoo.com.tw/car-topics/EV-and-Hybrid"
    assert {"PTS Taiwan EV News", "TechNews Automotive Technology"} <= names
    assert {"InsideEVs Charging", "Charged EVs", "The Driven"} <= names
    assert len(DEFAULT_SOURCES) >= 11


def test_yahoo_parser_accepts_article_slugs_and_deduplicates_links() -> None:
    raw_html = """
        <a href="/tesla-model-y-range-improves-033600101.html">Tesla Model Y 純電續航提升</a>
        <a href="/tesla-model-y-range-improves-033600101.html">重複連結</a>
        <a href="/car-topics/EV-and-Hybrid">電動車主題頁</a>
    """

    candidates = parse_yahoo_autos_candidates(raw_html, "https://autos.yahoo.com.tw", "autos.yahoo.com.tw", 10)

    assert len(candidates) == 1
    assert candidates[0].source_url.endswith("033600101.html")
    assert candidates[0].title == "Tesla Model Y 純電續航提升"


def test_yahoo_homepage_fallback_filters_non_ev_articles() -> None:
    raw_html = """
        <a href="/ford-kuga-update-033600101.html">Ford Kuga 新年式登場</a>
        <a href="/electric-id-buzz-033600102.html">VW ID.Buzz 純電車開始交付</a>
    """

    candidates = parse_yahoo_autos_candidates(
        raw_html,
        "https://autos.yahoo.com.tw",
        "autos.yahoo.com.tw",
        10,
        require_ev_keyword=True,
    )

    assert [candidate.title for candidate in candidates] == ["VW ID.Buzz 純電車開始交付"]


@pytest.mark.asyncio
async def test_yahoo_crawler_falls_back_to_filtered_homepage(monkeypatch: pytest.MonkeyPatch) -> None:
    topic_url = "https://autos.yahoo.com.tw/car-topics/EV-and-Hybrid"
    homepage_url = "https://autos.yahoo.com.tw"

    async def fake_fetch_text(url: str) -> tuple[str, str]:
        if url == topic_url:
            return "<html>consent</html>", "https://consent.yahoo.com/v2/collectConsent"
        assert url == homepage_url
        return (
            '<a href="/gas-car-033600101.html">一般燃油車新聞</a>'
            '<a href="/new-ev-033600102.html">全新純電休旅車正式發表</a>',
            homepage_url,
        )

    monkeypatch.setattr(yahoo_autos_crawler, "fetch_text", fake_fetch_text)

    result = await yahoo_autos_crawler.crawl_yahoo_autos(yahoo_source())

    assert len(result.candidates) == 1
    assert result.candidates[0].title == "全新純電休旅車正式發表"
    assert result.fallback_used["strategy"] == "homepage_ev_filter"
    assert result.fallback_used["attempts"][0]["status"] == "failed"
