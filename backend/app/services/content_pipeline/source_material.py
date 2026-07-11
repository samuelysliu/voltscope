import json
import re
from html import unescape
from html.parser import HTMLParser

from app.core.errors import AppError
from app.models import ContentCandidate, SourceWhitelist
from app.services.content_pipeline.crawlers.base import is_allowed_url, normalize_domain
from app.services.content_pipeline.crawlers.http_crawler import fetch_text


MIN_SOURCE_MATERIAL_CHARS = 500
MAX_SOURCE_MATERIAL_CHARS = 14_000

BOILERPLATE_PHRASES = (
    "accept cookies",
    "all rights reserved",
    "cookie policy",
    "privacy policy",
    "sign up for",
    "subscribe to",
)


def normalize_text(value: str) -> str:
    return " ".join(unescape(value or "").split())


class ArticleBodyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.article_depth = 0
        self.main_depth = 0
        self.paragraph_buffer: list[str] | None = None
        self.paragraph_is_scoped = False
        self.scoped_paragraphs: list[str] = []
        self.all_paragraphs: list[str] = []
        self.json_ld_buffer: list[str] | None = None
        self.json_ld_blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        name = tag.lower()
        attributes = {key.lower(): value for key, value in attrs}
        if name == "article":
            self.article_depth += 1
        elif name == "main":
            self.main_depth += 1
        elif name == "p":
            self.paragraph_buffer = []
            self.paragraph_is_scoped = self.article_depth > 0 or self.main_depth > 0
        elif name == "script" and "ld+json" in (attributes.get("type") or "").lower():
            self.json_ld_buffer = []

    def handle_endtag(self, tag: str) -> None:
        name = tag.lower()
        if name == "p" and self.paragraph_buffer is not None:
            paragraph = normalize_text("".join(self.paragraph_buffer))
            if paragraph:
                self.all_paragraphs.append(paragraph)
                if self.paragraph_is_scoped:
                    self.scoped_paragraphs.append(paragraph)
            self.paragraph_buffer = None
            self.paragraph_is_scoped = False
        elif name == "script" and self.json_ld_buffer is not None:
            self.json_ld_blocks.append("".join(self.json_ld_buffer))
            self.json_ld_buffer = None
        elif name == "article" and self.article_depth:
            self.article_depth -= 1
        elif name == "main" and self.main_depth:
            self.main_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.paragraph_buffer is not None:
            self.paragraph_buffer.append(data)
        if self.json_ld_buffer is not None:
            self.json_ld_buffer.append(data)


def json_article_bodies(value: object) -> list[str]:
    if isinstance(value, list):
        return [body for item in value for body in json_article_bodies(item)]
    if not isinstance(value, dict):
        return []
    bodies: list[str] = []
    article_body = value.get("articleBody")
    if isinstance(article_body, str):
        bodies.append(normalize_text(article_body))
    for key in ("@graph", "mainEntity", "itemListElement"):
        if key in value:
            bodies.extend(json_article_bodies(value[key]))
    return bodies


def useful_paragraphs(paragraphs: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for paragraph in paragraphs:
        normalized = normalize_text(paragraph)
        lowered = normalized.lower()
        if len(normalized) < 60 or any(phrase in lowered for phrase in BOILERPLATE_PHRASES):
            continue
        fingerprint = re.sub(r"\W+", "", lowered)
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append(normalized)
    return result


def extract_article_text(raw_html: str) -> str:
    parser = ArticleBodyParser()
    parser.feed(raw_html)

    json_bodies: list[str] = []
    for block in parser.json_ld_blocks:
        try:
            json_bodies.extend(json_article_bodies(json.loads(block)))
        except (json.JSONDecodeError, TypeError):
            continue
    if json_bodies:
        material = "\n\n".join(useful_paragraphs(json_bodies))
        if len(material) >= MIN_SOURCE_MATERIAL_CHARS:
            return material[:MAX_SOURCE_MATERIAL_CHARS]

    scoped = useful_paragraphs(parser.scoped_paragraphs)
    paragraphs = scoped if len("\n\n".join(scoped)) >= MIN_SOURCE_MATERIAL_CHARS else useful_paragraphs(parser.all_paragraphs)
    return "\n\n".join(paragraphs)[:MAX_SOURCE_MATERIAL_CHARS]


def source_domain(candidate: ContentCandidate) -> str:
    source = candidate.__dict__.get("source")
    if isinstance(source, SourceWhitelist):
        return normalize_domain(source.domain)
    return normalize_domain(candidate.source_url)


async def fetch_candidate_source_material(candidate: ContentCandidate) -> str:
    try:
        raw_html, final_url = await fetch_text(candidate.source_url)
        if not is_allowed_url(final_url, source_domain(candidate)):
            raise AppError("SOURCE_REDIRECT_NOT_ALLOWED", "Source article redirected outside the approved domain", 422)
        extracted = extract_article_text(raw_html)
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            "SOURCE_ARTICLE_FETCH_FAILED",
            "Unable to read the original article, so generation was stopped",
            422,
            {"reason": str(exc)[:500]},
        ) from exc

    if len(extracted) < MIN_SOURCE_MATERIAL_CHARS:
        raise AppError(
            "SOURCE_MATERIAL_INSUFFICIENT",
            "The source article does not contain enough factual material to generate a publishable report",
            422,
            {"characters": len(extracted), "minimum": MIN_SOURCE_MATERIAL_CHARS},
        )
    return extracted[:MAX_SOURCE_MATERIAL_CHARS]
