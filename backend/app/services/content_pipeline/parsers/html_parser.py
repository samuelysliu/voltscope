import re
from html import unescape
from html.parser import HTMLParser

from app.services.content_pipeline.crawlers.base import CrawledCandidate, absolute_allowed_url

SKIP_PREFIXES = ("#", "mailto:", "tel:", "javascript:")
SKIP_PARTS = (
    "/about",
    "/advert",
    "/author",
    "/category",
    "/contact",
    "/login",
    "/privacy",
    "/search",
    "/tag/",
    "/terms",
)

YAHOO_AUTOS_LATIN_EV_KEYWORDS = ("bev", "electric", "ev", "hybrid", "phev")
YAHOO_AUTOS_CJK_EV_KEYWORDS = ("充電", "油電", "純電", "電動", "電池")
LOW_QUALITY_LINK_TEXT = ("read more", "繼續閱讀", "觀看次數", "閱讀更多")


class ArticleLinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_link = False
        self.current_href: str | None = None
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        self.in_link = True
        self.current_href = href
        self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.in_link:
            return
        title = " ".join("".join(self.current_text).split())
        if self.current_href and title:
            self.links.append((self.current_href, unescape(title)))
        self.in_link = False
        self.current_href = None
        self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.in_link:
            self.current_text.append(data)


class EvoasisListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.div_depth = 0
        self.item_depth: int | None = None
        self.links: list[str] = []
        self.headings: list[str] = []
        self.paragraphs: list[str] = []
        self.text_buffer: list[str] | None = None
        self.text_kind: str | None = None
        self.items: list[tuple[str, str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        attributes = {key.lower(): value for key, value in attrs}
        if name == "div":
            self.div_depth += 1
            classes = (attributes.get("class") or "").split()
            if self.item_depth is None and "wixui-repeater__item" in classes:
                self.item_depth = self.div_depth
                self.links = []
                self.headings = []
                self.paragraphs = []
        if self.item_depth is None:
            return
        if name == "a":
            href = attributes.get("href") or ""
            if "/latestnews/" in href and not href.rstrip("/").endswith("/latestnews/list"):
                self.links.append(href)
        elif name in {"h1", "h2", "h3"}:
            self.text_kind = "heading"
            self.text_buffer = []
        elif name == "p":
            self.text_kind = "paragraph"
            self.text_buffer = []

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if self.item_depth is not None and self.text_buffer is not None:
            if self.text_kind == "heading" and name in {"h1", "h2", "h3"}:
                self._finish_text(self.headings)
            elif self.text_kind == "paragraph" and name == "p":
                self._finish_text(self.paragraphs)
        if name != "div":
            return
        if self.item_depth == self.div_depth:
            self._finish_item()
        self.div_depth = max(0, self.div_depth - 1)

    def handle_data(self, data: str) -> None:
        if self.item_depth is not None and self.text_buffer is not None:
            self.text_buffer.append(data)

    def _finish_text(self, destination: list[str]) -> None:
        text = " ".join("".join(self.text_buffer or []).split())
        if text:
            destination.append(unescape(text))
        self.text_buffer = None
        self.text_kind = None

    def _finish_item(self) -> None:
        if self.links and self.headings:
            title = max(self.headings, key=len)
            excerpt = max(self.paragraphs, key=len) if self.paragraphs else None
            self.items.append((self.links[0], title, excerpt))
        self.item_depth = None
        self.links = []
        self.headings = []
        self.paragraphs = []
        self.text_buffer = None
        self.text_kind = None


def _looks_like_article(url: str, title: str) -> bool:
    lower = url.lower()
    if lower.startswith(SKIP_PREFIXES) or any(part in lower for part in SKIP_PARTS):
        return False
    if len(title) < 6:
        return False
    return any(char.isdigit() for char in lower) or any(part in lower for part in ("/news", "/article", "/blog", "/post", "/story"))


def _title_quality(title: str) -> int:
    lowered = title.lower()
    penalty = 200 if any(label in lowered for label in LOW_QUALITY_LINK_TEXT) else 0
    return min(len(title), 120) - penalty


def _contains_yahoo_ev_keyword(title: str) -> bool:
    lowered = title.lower()
    if any(keyword in lowered for keyword in YAHOO_AUTOS_CJK_EV_KEYWORDS):
        return True
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", lowered)
        for keyword in YAHOO_AUTOS_LATIN_EV_KEYWORDS
    )


def parse_html_candidates(raw_html: str, base_url: str, allowed_domain: str, limit: int) -> list[CrawledCandidate]:
    parser = ArticleLinkParser()
    parser.feed(raw_html)
    ordered_urls: list[str] = []
    best_title_by_url: dict[str, str] = {}
    for href, title in parser.links:
        if not _looks_like_article(href, title):
            continue
        source_url = absolute_allowed_url(href, base_url, allowed_domain)
        if not source_url:
            continue
        current_title = best_title_by_url.get(source_url)
        if current_title is None:
            ordered_urls.append(source_url)
        if current_title is None or _title_quality(title) > _title_quality(current_title):
            best_title_by_url[source_url] = title

    candidates: list[CrawledCandidate] = []
    for source_url in ordered_urls[:limit]:
        candidates.append(
            CrawledCandidate(
                source_url=source_url,
                title=best_title_by_url[source_url][:500],
                parser_type="html",
                confidence_score=0.55,
            )
        )
    return candidates


def parse_evoasis_candidates(raw_html: str, base_url: str, allowed_domain: str, limit: int) -> list[CrawledCandidate]:
    parser = EvoasisListParser()
    parser.feed(raw_html)
    candidates: list[CrawledCandidate] = []
    seen: set[str] = set()
    for href, title, excerpt in parser.items:
        source_url = absolute_allowed_url(href, base_url, allowed_domain)
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        candidates.append(
            CrawledCandidate(
                source_url=source_url,
                title=title[:500],
                excerpt=excerpt[:500] if excerpt else None,
                parser_type="html",
                confidence_score=0.9,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates


def parse_yahoo_autos_candidates(
    raw_html: str,
    base_url: str,
    allowed_domain: str,
    limit: int,
    require_ev_keyword: bool = False,
) -> list[CrawledCandidate]:
    parser = ArticleLinkParser()
    parser.feed(raw_html)
    candidates: list[CrawledCandidate] = []
    seen: set[str] = set()
    for href, title in parser.links:
        source_url = absolute_allowed_url(href, base_url, allowed_domain)
        if not source_url or not source_url.lower().split("?", 1)[0].endswith(".html"):
            continue
        normalized_title = " ".join(title.split())
        lowered_title = normalized_title.lower()
        if require_ev_keyword and not _contains_yahoo_ev_keyword(lowered_title):
            continue
        if source_url in seen:
            continue
        seen.add(source_url)
        candidates.append(
            CrawledCandidate(
                source_url=source_url,
                title=normalized_title[:500],
                parser_type="html",
                confidence_score=0.8 if not require_ev_keyword else 0.7,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates
