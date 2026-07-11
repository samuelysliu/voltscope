from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
import re
import xml.etree.ElementTree as ET

from app.services.content_pipeline.crawlers.base import CrawledCandidate, absolute_allowed_url

TAG_RE = re.compile(r"<[^>]+>")


def _text(node: ET.Element, names: list[str]) -> str | None:
    lower_names = {name.lower() for name in names}
    for name in names:
        found = node.find(name)
        if found is not None and found.text and found.text.strip():
            return unescape(found.text.strip())
    for child in node:
        local_name = child.tag.split("}", 1)[-1].lower()
        if local_name in lower_names and child.text and child.text.strip():
            return unescape(child.text.strip())
    return None


def _atom_link(node: ET.Element) -> str | None:
    for child in node:
        local_name = child.tag.split("}", 1)[-1].lower()
        if local_name == "link":
            href = child.attrib.get("href")
            if href:
                return href
    return None


def _clean_summary(value: str | None) -> str | None:
    if not value:
        return None
    text = TAG_RE.sub(" ", value)
    text = " ".join(unescape(text).split())
    return text[:500] if text else None


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def parse_rss_candidates(raw_xml: str, base_url: str, allowed_domain: str, limit: int) -> list[CrawledCandidate]:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return []

    nodes = root.findall(".//item")
    if not nodes:
        nodes = [node for node in root.iter() if node.tag.split("}", 1)[-1].lower() == "entry"]

    candidates: list[CrawledCandidate] = []
    seen: set[str] = set()
    for node in nodes:
        title = _text(node, ["title"])
        link = _text(node, ["link"]) or _atom_link(node)
        if not title or not link:
            continue
        source_url = absolute_allowed_url(link, base_url, allowed_domain)
        if not source_url or source_url in seen:
            continue
        seen.add(source_url)
        summary = _text(node, ["description", "summary", "content", "encoded"])
        published = _text(node, ["pubDate", "published", "updated", "date"])
        author = _text(node, ["author", "creator"])
        candidates.append(
            CrawledCandidate(
                source_url=source_url,
                title=" ".join(title.split())[:500],
                excerpt=_clean_summary(summary),
                published_at=_parse_datetime(published),
                author=author,
                parser_type="rss",
                confidence_score=0.95,
            )
        )
        if len(candidates) >= limit:
            break
    return candidates
