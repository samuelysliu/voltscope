from types import SimpleNamespace
from typing import cast

import pytest

from app.models import SourceWhitelist
from app.services.article_classification import TOPIC_RULES, score_rules
from app.services.content_pipeline.crawlers import crawler_fallback
from app.services.content_pipeline.parsers.html_parser import parse_evoasis_candidates, parse_html_candidates
from app.services.content_pipeline.parsers.rss_parser import parse_rss_candidates
from app.services.content_pipeline.source_material import MIN_SOURCE_MATERIAL_CHARS, extract_article_text
from scripts.seed_content_sources import DEFAULT_SOURCES


def source(**overrides: object) -> SourceWhitelist:
    values = {
        "domain": "evoasis.com.tw",
        "list_url": "https://www.evoasis.com.tw/latestnews/list",
        "homepage_url": "https://www.evoasis.com.tw",
        "max_candidates_per_run": 10,
    }
    values.update(overrides)
    return cast(SourceWhitelist, SimpleNamespace(**values))


def test_source_catalog_disables_yahoo_and_adds_required_sources() -> None:
    catalog = {item["name"]: item for item in DEFAULT_SOURCES}
    expected = {
        "EVOASIS News",
        "U-POWER News",
        "TAIL News",
        "Battway EV News",
        "TechNews Energy",
        "TechNews Energy Storage",
    }

    assert catalog["Yahoo Taiwan Autos EV"]["enabled"] is False
    assert catalog["Yahoo Taiwan Autos EV"]["force_disabled"] is True
    assert expected <= catalog.keys()
    assert catalog["EVOASIS News"]["list_url"] == "https://www.evoasis.com.tw/latestnews/list"
    assert catalog["TechNews Energy"]["rss_url"].endswith("%E7%A7%91%E6%8A%80/feed/")
    assert catalog["TechNews Energy Storage"]["rss_url"].endswith("%E5%84%B2%E5%AD%98/feed/")
    assert all(catalog[name]["requires_review"] is True for name in expected)
    assert all(catalog[name]["allow_auto_publish"] is False for name in expected)


def test_evoasis_parser_uses_article_heading_instead_of_read_more() -> None:
    raw_html = """
        <div class="gallery-item wixui-repeater__item">
          <a href="/latestnews/charging-network"><img alt="充電網路"></a>
          <h2><span>媒體報導</span></h2>
          <h2><span>EVOASIS 攜手夥伴打造全台最大充電網</span></h2>
          <p>跨品牌充電互通正式啟動，擴大快速充電服務涵蓋範圍。</p>
          <a href="/latestnews/charging-network">Read More &gt;</a>
        </div>
    """

    candidates = parse_evoasis_candidates(
        raw_html,
        "https://www.evoasis.com.tw/latestnews/list",
        "evoasis.com.tw",
        10,
    )

    assert len(candidates) == 1
    assert candidates[0].title == "EVOASIS 攜手夥伴打造全台最大充電網"
    assert candidates[0].excerpt == "跨品牌充電互通正式啟動，擴大快速充電服務涵蓋範圍。"
    assert candidates[0].source_url == "https://www.evoasis.com.tw/latestnews/charging-network"


@pytest.mark.asyncio
async def test_evoasis_crawler_uses_structured_parser(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_html = """
        <div class="wixui-repeater__item">
          <a href="/latestnews/new-station"></a>
          <h2>全新高速充電站正式啟用</h2>
          <p>新站點提供多支快充槍，改善區域充電需求。</p>
          <a href="/latestnews/new-station">Read More &gt;</a>
        </div>
    """

    async def fake_fetch_text(url: str) -> tuple[str, str]:
        return raw_html, url

    monkeypatch.setattr(crawler_fallback, "fetch_text", fake_fetch_text)

    result = await crawler_fallback.crawl_static_html(source())

    assert result.fallback_used["status"] == "success"
    assert [candidate.title for candidate in result.candidates] == ["全新高速充電站正式啟用"]


@pytest.mark.parametrize(
    ("base_url", "domain", "href", "title"),
    [
        ("https://www.u-power.com.tw/news.html", "u-power.com.tw", "/news/news-20260701.html", "U-POWER 新充電站正式啟用"),
        ("https://www.evtail.com.tw/posts/list/news", "evtail.com.tw", "/posts/detail/news-123", "特爾電力推出全新充電服務"),
        ("https://www.battway.com.tw/", "battway.com.tw", "/news/2026/07/charging", "台灣充電網路最新發展"),
    ],
)
def test_required_html_sources_produce_candidates(base_url: str, domain: str, href: str, title: str) -> None:
    candidates = parse_html_candidates(f'<a href="{href}">{title}</a>', base_url, domain, 10)

    assert len(candidates) == 1
    assert candidates[0].title == title
    assert candidates[0].source_url.startswith(f"https://www.{domain}/")


def test_html_parser_prefers_article_title_over_date_for_duplicate_url() -> None:
    raw_html = """
        <a href="/posts/detail/news-123">Jun 18, 2026 | 觀看次數：447</a>
        <a href="/posts/detail/news-123">特爾電力推出全新跨網充電服務計畫</a>
        <a href="/posts/detail/news-123">繼續閱讀</a>
    """

    candidates = parse_html_candidates(raw_html, "https://www.evtail.com.tw/posts/list/news", "evtail.com.tw", 10)

    assert [candidate.title for candidate in candidates] == ["特爾電力推出全新跨網充電服務計畫"]


def test_technews_energy_rss_produces_candidate_with_metadata() -> None:
    raw_xml = """
        <rss version="2.0"><channel><item>
          <title>台灣儲能系統加入電網調度</title>
          <link>https://technews.tw/2026/07/16/energy-storage-grid/</link>
          <description><![CDATA[儲能設備可協助平衡尖峰用電。]]></description>
          <pubDate>Thu, 16 Jul 2026 08:00:00 +0800</pubDate>
        </item></channel></rss>
    """

    candidates = parse_rss_candidates(raw_xml, "https://technews.tw/", "technews.tw", 10)

    assert len(candidates) == 1
    assert candidates[0].title == "台灣儲能系統加入電網調度"
    assert candidates[0].excerpt == "儲能設備可協助平衡尖峰用電。"
    assert candidates[0].published_at is not None


def test_source_article_body_is_long_enough_for_generation() -> None:
    paragraphs = "".join(
        f"<p>第 {index} 段說明充電設施與能源系統的建置、營運及安全管理細節，"
        "並列出站點容量、設備規格、執行時程與合作單位，提供可核對的完整事實內容。</p>"
        for index in range(20)
    )

    extracted = extract_article_text(f"<main>{paragraphs}</main>")

    assert len(extracted) >= MIN_SOURCE_MATERIAL_CHARS


def test_energy_and_storage_articles_receive_specific_topic_scores() -> None:
    storage_scores = score_rules("大型儲能系統投入電力儲存與電網級電池服務", TOPIC_RULES)
    energy_scores = score_rules("離岸風電與太陽能推動再生能源及能源轉型", TOPIC_RULES)
    charging_brand_scores = score_rules("特爾電力宣布新的快速充電站與充電優惠", TOPIC_RULES)

    assert storage_scores["energy-storage"] > 0
    assert energy_scores["energy"] > 0
    assert charging_brand_scores["charging-station"] > charging_brand_scores["energy"]
