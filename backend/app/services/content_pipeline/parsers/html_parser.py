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


def _looks_like_article(url: str, title: str) -> bool:
    lower = url.lower()
    if lower.startswith(SKIP_PREFIXES) or any(part in lower for part in SKIP_PARTS):
        return False
    if len(title) < 6:
        return False
    return any(char.isdigit() for char in lower) or any(part in lower for part in ("/news", "/article", "/blog", "/post", "/story"))


def parse_html_candidates(raw_html: str, base_url: str, allowed_domain: str, limit: int) -> list[CrawledCandidate]:
    parser = ArticleLinkParser()
    parser.feed(raw_html)
    candidates: list[CrawledCandidate] = []
    seen: set[str] = set()
    for href, title in parser.links:
        if not _looks_like_article(href, title):
            continue
        source_url = absolute_allowed_url(href, base_url, allowed_domain)
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        candidates.append(
            CrawledCandidate(
                source_url=source_url,
                title=title[:500],
                parser_type="html",
                confidence_score=0.55,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates
