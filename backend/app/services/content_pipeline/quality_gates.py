from difflib import SequenceMatcher
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

from app.core.config import get_settings
from app.models import ContentCandidate, SourceWhitelist


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(text.split())


def domain(value: str) -> str:
    parsed = urlparse(value)
    host = (parsed.netloc or parsed.path).lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def loaded_source(candidate: ContentCandidate) -> SourceWhitelist | None:
    source = candidate.__dict__.get("source")
    return source if isinstance(source, SourceWhitelist) else None


def token_set(value: str) -> set[str]:
    return {item for item in re.findall(r"[a-z0-9]{3,}", value.lower()) if item}


def token_list(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]{3,}", value.lower())


def source_phrases(candidate: ContentCandidate) -> list[str]:
    text = " ".join(
        item
        for item in [candidate.source_excerpt or "", candidate.raw_text_excerpt or ""]
        if item
    )
    parts = re.split(r"[.!?\n]+", text)
    return [" ".join(part.split()) for part in parts if len(" ".join(part.split())) >= 50 or len(token_set(part)) >= 12]


def sentence_overlap_ratio(candidate: ContentCandidate, article_text: str) -> float:
    article_sentences = [
        " ".join(part.split())
        for part in re.split(r"[.!?\n]+", strip_html(article_text).lower())
        if len(token_list(part)) >= 5
    ]
    max_ratio = 0.0
    for phrase in source_phrases(candidate):
        normalized = phrase.lower()
        phrase_tokens = token_list(normalized)
        if not phrase_tokens:
            continue
        for sentence in article_sentences:
            if normalized and normalized in sentence:
                return 1.0
            sentence_tokens = token_list(sentence)
            match = SequenceMatcher(None, phrase_tokens, sentence_tokens, autojunk=False).find_longest_match()
            if match.size >= 8:
                max_ratio = max(max_ratio, match.size / len(phrase_tokens))
    return round(max_ratio, 4)


def has_source_attribution(candidate: ContentCandidate, html_values: list[str]) -> bool:
    expected_url = (candidate.canonical_url or candidate.source_url).rstrip("/")
    parser = LinkParser()
    for html in html_values:
        parser.feed(html or "")
    normalized_links = [link.rstrip("/") for link in parser.links]
    return expected_url in normalized_links or candidate.source_url.rstrip("/") in normalized_links


def count_zh_chars(value: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", value))


def count_en_words(value: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", value))


# These phrases identify the generic copy pattern described in bug.md.
GENERIC_ARTICLE_PHRASES = (
    "\u5f15\u767c\u96fb\u52d5\u8eca\u5e02\u5834\u95dc\u6ce8",
    "\u672c\u6b21\u8a0a\u606f\u7684\u6838\u5fc3\u5728\u65bc",
    "\u9019\u985e\u8a0a\u606f\u4e0d\u53ea\u662f",
    "\u4e0d\u4e00\u5b9a\u6703\u76f4\u63a5\u5f71\u97ff\u53f0\u7063",
    "\u767c\u5e03\u524d\u61c9\u9032\u4e00\u6b65\u6838\u5c0d",
    "\u7de8\u8f2f\u53ef\u518d\u88dc\u5145",
    "\u5f85\u5be9\u7a3f",
    "\u5f8c\u7e8c\u82e5\u51fa\u73fe\u9023\u52d5",
    "\u5831\u5c0e\u91cd\u9ede",
    "\u7522\u696d\u8108\u7d61",
    "\u5c0d\u53f0\u7063\u8207\u5145\u96fb\u5e02\u5834\u7684\u53c3\u8003",
    "\u5f8c\u7e8c\u89c0\u5bdf",
    "public information from",
    "editors should verify",
    "for editorial review",
    "market relevance",
    "what to watch",
)


def issue(code: str, severity: str, message: str, **meta) -> dict:
    data = {"code": code, "severity": severity, "message": message}
    data.update(meta)
    return data


def run_quality_gates(
    candidate: ContentCandidate,
    zh_payload: dict,
    en_payload: dict,
    image_urls: list[str] | None = None,
) -> dict:
    settings = get_settings()
    issues: list[dict] = []
    metrics: dict[str, object] = {}

    for locale, payload in (("zh-TW", zh_payload), ("en", en_payload)):
        for key in ("title", "excerpt", "html", "text", "seo_title", "seo_description"):
            if not payload.get(key):
                issues.append(issue("missing_required_field", "critical", "Generated article is missing a required field", locale=locale, field=key))

    source = loaded_source(candidate)
    source_domain = source.domain if source is not None else domain(candidate.source_url)
    if domain(candidate.source_url) != source_domain and not domain(candidate.source_url).endswith(f".{source_domain}"):
        issues.append(issue("source_url_not_whitelisted", "critical", "Candidate URL is outside the source whitelist domain"))

    if not has_source_attribution(candidate, [zh_payload.get("html", ""), en_payload.get("html", "")]):
        issues.append(issue("missing_source_attribution", "critical", "Generated article must link back to the source URL or source domain"))

    notes = candidate.factual_notes or {}
    if notes.get("should_publish") is False:
        issues.append(issue("factual_notes_should_not_publish", "critical", "Factual notes marked this candidate as unsuitable for publishing"))
    verified_facts = notes.get("verified_facts")
    metrics["verified_fact_count"] = len(verified_facts) if isinstance(verified_facts, list) else 0
    if not isinstance(verified_facts, list) or len(verified_facts) < 3:
        issues.append(issue("insufficient_verified_facts", "critical", "At least three verified source facts are required"))

    combined_text = " ".join(
        [
            zh_payload.get("text", ""),
            en_payload.get("text", ""),
            strip_html(zh_payload.get("html", "")),
            strip_html(en_payload.get("html", "")),
        ]
    )
    overlap = sentence_overlap_ratio(candidate, combined_text)
    metrics["max_source_sentence_overlap"] = overlap
    if overlap > settings.content_pipeline_max_source_sentence_overlap:
        issues.append(issue("source_sentence_overlap_too_high", "critical", "Generated article overlaps too closely with source text", value=overlap, threshold=settings.content_pipeline_max_source_sentence_overlap))

    zh_chars = count_zh_chars(zh_payload.get("text", ""))
    en_words = count_en_words(en_payload.get("text", ""))
    metrics["zh_chars"] = zh_chars
    metrics["en_words"] = en_words
    if zh_chars < settings.content_pipeline_min_zh_chars:
        issues.append(issue("zh_article_short", "critical", "Chinese article is shorter than the publishable minimum", locale="zh-TW", value=zh_chars, target=settings.content_pipeline_min_zh_chars))
    if en_words < settings.content_pipeline_min_en_words:
        issues.append(issue("en_article_short", "critical", "English article is shorter than the publishable minimum", locale="en", value=en_words, target=settings.content_pipeline_min_en_words))

    zh_title = zh_payload.get("title", "")
    zh_title_chars = count_zh_chars(zh_title)
    latin_title_chars = len(re.findall(r"[A-Za-z]", zh_title))
    zh_title_ratio = zh_title_chars / max(1, zh_title_chars + latin_title_chars)
    metrics["zh_title_chars"] = zh_title_chars
    metrics["zh_title_ratio"] = round(zh_title_ratio, 4)
    if zh_title_chars < 8 or zh_title_ratio < 0.25:
        issues.append(issue("zh_title_not_localized", "critical", "Chinese headline must communicate the event in Traditional Chinese"))
    if len(candidate.source_title) >= 20 and candidate.source_title.lower() in zh_title.lower():
        issues.append(issue("zh_title_contains_source_title", "critical", "Chinese headline must not reuse the complete English source headline"))

    combined_lower = combined_text.lower()
    matched_generic_phrases = [phrase for phrase in GENERIC_ARTICLE_PHRASES if phrase.lower() in combined_lower]
    metrics["generic_phrase_matches"] = matched_generic_phrases
    if matched_generic_phrases:
        issues.append(issue("generic_article_template_detected", "critical", "Generated article contains generic template or editorial-process language", phrases=matched_generic_phrases))

    for image_url in image_urls or []:
        if image_url and domain(image_url) == domain(candidate.source_url):
            issues.append(issue("source_image_hotlink", "critical", "Generated article must not hotlink source images", image_url=image_url))

    critical_count = len([item for item in issues if item["severity"] == "critical"])
    warning_count = len([item for item in issues if item["severity"] == "warning"])
    return {
        "pass": critical_count == 0,
        "issues": issues,
        "metrics": metrics,
        "critical_count": critical_count,
        "warning_count": warning_count,
        "recommendation": "ready_for_review" if critical_count == 0 else "failed_quality_gate",
    }
