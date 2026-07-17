import json

from app.core.config import get_settings
from app.models import ContentCandidate


def article_length_requirement(locale: str) -> tuple[int, str]:
    settings = get_settings()
    if locale == "zh-TW":
        minimum = settings.content_pipeline_min_zh_chars
        target = max(minimum + 50, 650)
        return minimum, f"at least {target} CJK characters"
    minimum = settings.content_pipeline_min_en_words
    target = max(minimum + 30, int(minimum * 1.15))
    return minimum, f"at least {target} English words"


def candidate_context(candidate: ContentCandidate, source_material: str | None = None) -> str:
    fields = [
        f"source_title: {candidate.source_title}",
        f"source_url: {candidate.source_url}",
        f"source_excerpt: {candidate.source_excerpt or ''}",
        f"source_author: {candidate.source_author or ''}",
        f"source_published_at: {candidate.source_published_at.isoformat() if candidate.source_published_at else ''}",
        f"quota_category: {candidate.quota_category}",
        f"relevance_score: {candidate.relevance_score}",
        f"novelty_score: {candidate.novelty_score}",
    ]
    if source_material:
        fields.append(f"source_article_body:\n{source_material}")
    return "\n".join(fields)


def factual_notes_messages(candidate: ContentCandidate, source_material: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You extract factual notes for VoltScope, an EV, charging, and smart mobility publication. "
                "Return strict JSON only. Treat the supplied source article as the sole factual record. "
                "Do not add common knowledge, predictions, Taiwan relevance, or market impact unless the source supports it. "
                "Separate verified statements from allegations, estimates, and unknown details."
            ),
        },
        {
            "role": "user",
            "content": (
                "Extract JSON with keys: entities, dates, numbers, locations, products, verified_facts, "
                "attributed_claims, uncertain_claims, missing_context, source_attribution, should_publish, reason. "
                "verified_facts must preserve the concrete who, what, when, where, quantity, cause, consequence, "
                "affected models or populations, and official response found in the source. Set should_publish=false "
                "when fewer than three concrete facts can be established. Keep entities, dates, numbers, locations, "
                "and products to at most 12 items each. Keep verified_facts to 5-12 concise items, attributed_claims "
                "and uncertain_claims to at most 8 items each, and missing_context to at most 6 items. Do not repeat "
                "the source article or include prose outside the JSON object.\n\n"
                f"{candidate_context(candidate, source_material)}"
            ),
        },
    ]


def article_generation_messages(
    candidate: ContentCandidate,
    factual_notes: dict,
    locale: str,
    source_material: str | None = None,
) -> list[dict[str, str]]:
    language = "Traditional Chinese" if locale == "zh-TW" else "English"
    minimum, length_requirement = article_length_requirement(locale)
    unit = "CJK characters" if locale == "zh-TW" else "English words"
    return [
        {
            "role": "system",
            "content": (
                "You are a senior reporter for VoltScope, an EV and charging news publication. Return strict JSON only. "
                "Write a fact-dense, original news story from the supplied factual record. Never pad the article with "
                "generic EV-market commentary, a meeting-summary structure, or unsupported Taiwan relevance. "
                "Attribute claims to their speaker or source, distinguish facts from uncertainty, and do not copy source sentences. "
                "For Traditional Chinese, use natural Taiwan news language and translate the semantic meaning of the headline. "
                "Company and product names may remain in English, but an English headline followed by a generic Chinese suffix is invalid. "
                "For example, the headline 'Ford Recalls 43,000 Mustang Mach-E EVs Over Diffs That May Go Bang' should become "
                "'Ford \u53ec\u56de 4.3 \u842c\u8f1b Mustang Mach-E\uff0c"
                "\u5dee\u901f\u5668\u7570\u5e38\u6050\u767c\u51fa\u7206\u88c2\u8072', not the English title plus "
                "Chinese filler."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Write a {language} article. Return JSON with keys: title, slug, excerpt, html, text, "
                "seo_title, seo_description. Use p, h2, and a tags in HTML. Include one source link using the exact source_url. "
                f"The article body in both html and text must contain {length_requirement}; the publication gate is {minimum} {unit}. "
                "Count the article body before responding and aim above the gate, but never invent facts to reach length. "
                "Open with the most newsworthy verified event and its concrete scale or consequence. Follow with evidence, "
                "chronology, technical or regulatory context explicitly present in the notes, affected stakeholders, and the "
                "official response. "
                "Use descriptive h2 headings only when they improve a long article; never use generic headings such as Report Highlights, "
                "Industry Context, Taiwan Relevance, or What to Watch. Omit Taiwan entirely unless the factual notes establish "
                "a direct connection. "
                "Do not mention drafts, editors, verification before publication, missing information, or the writing process. "
                "The excerpt must state the event and its most important consequence in one or two specific sentences.\n\n"
                f"Candidate and source material:\n{candidate_context(candidate, source_material)}\n\n"
                f"Factual record:\n{json.dumps(factual_notes, ensure_ascii=False)}"
            ),
        },
    ]


def article_revision_messages(
    candidate: ContentCandidate,
    factual_notes: dict,
    locale: str,
    draft: dict,
    issue_codes: list[str],
    quality_metrics: dict | None = None,
) -> list[dict[str, str]]:
    language = "Traditional Chinese" if locale == "zh-TW" else "English"
    minimum, length_requirement = article_length_requirement(locale)
    current_length = (quality_metrics or {}).get("zh_chars" if locale == "zh-TW" else "en_words", "unknown")
    unit = "CJK characters" if locale == "zh-TW" else "English words"
    return [
        {
            "role": "system",
            "content": (
                "You are the senior copy editor for VoltScope. Return strict JSON only. Rewrite the entire draft so it passes "
                "the listed quality checks while staying strictly within the factual record. Add useful factual explanation, chronology, "
                "attribution, and consequences already supported by the notes. Never add generic market padding or unsupported claims."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Rewrite this {language} article. Return all keys: title, slug, excerpt, html, text, seo_title, seo_description. "
                f"The current article has {current_length} {unit}; the publication minimum is {minimum}. "
                f"Rewrite the complete article to contain {length_requirement} in both html and text, and count only the article body. "
                "Do not summarize or shorten sections that are supported by the factual record. Use p, h2, and a tags in HTML, "
                f"and include the exact source URL {candidate.source_url}. For Traditional Chinese, the headline must state the event "
                "in natural Taiwan news language rather than retaining the English source headline. Do not mention the editing process, "
                "missing context, or Taiwan unless the facts directly involve Taiwan.\n\n"
                f"Failed checks: {json.dumps(issue_codes)}\n\n"
                f"Factual record: {json.dumps(factual_notes, ensure_ascii=False)}\n\n"
                f"Draft to rewrite: {json.dumps(draft, ensure_ascii=False)}"
            ),
        },
    ]


def article_translation_messages(
    candidate: ContentCandidate,
    factual_notes: dict,
    zh_article: dict,
) -> list[dict[str, str]]:
    minimum, length_requirement = article_length_requirement("en")
    return [
        {
            "role": "system",
            "content": (
                "You are a professional news translator for VoltScope. Translate the finalized Traditional Chinese article "
                "into natural English. The Chinese article is the master copy: preserve every supported fact, number, date, "
                "attribution, qualification, paragraph, and sequence. Do not independently regenerate the story from the source, "
                "add analysis, omit details, or summarize the article. Return strict JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "Translate the complete Chinese master into English. Return all keys: title, slug, excerpt, html, text, "
                "seo_title, seo_description. Preserve the article structure with p, h2, and a tags and retain the exact source "
                f"URL {candidate.source_url}. The English body must contain {length_requirement}; the publication gate is "
                f"{minimum} English words. Translate every substantive Chinese paragraph instead of shortening it. The factual "
                "record is supplied only to prevent translation errors, not as permission to independently rewrite the report.\n\n"
                f"Factual record: {json.dumps(factual_notes, ensure_ascii=False)}\n\n"
                f"Finalized Chinese master: {json.dumps(zh_article, ensure_ascii=False)}"
            ),
        },
    ]


def article_translation_revision_messages(
    candidate: ContentCandidate,
    factual_notes: dict,
    zh_article: dict,
    en_article: dict,
    issue_codes: list[str],
    quality_metrics: dict | None = None,
) -> list[dict[str, str]]:
    minimum, length_requirement = article_length_requirement("en")
    current_length = (quality_metrics or {}).get("en_words", "unknown")
    return [
        {
            "role": "system",
            "content": (
                "You correct an English translation against its finalized Traditional Chinese master. Return strict JSON only. "
                "Restore every omitted fact and paragraph from the Chinese article without adding unsupported information."
            ),
        },
        {
            "role": "user",
            "content": (
                "Return all keys: title, slug, excerpt, html, text, seo_title, seo_description. The current English translation "
                f"has {current_length} English words and failed {json.dumps(issue_codes)}. Produce {length_requirement}; the "
                f"publication gate is {minimum}. Preserve p, h2, and a tags and the exact source URL {candidate.source_url}. "
                "Translate every substantive paragraph in the Chinese master and do not independently regenerate or summarize it.\n\n"
                f"Factual record: {json.dumps(factual_notes, ensure_ascii=False)}\n\n"
                f"Finalized Chinese master: {json.dumps(zh_article, ensure_ascii=False)}\n\n"
                f"English translation to correct: {json.dumps(en_article, ensure_ascii=False)}"
            ),
        },
    ]


def article_review_messages(
    candidate: ContentCandidate,
    factual_notes: dict,
    locale: str,
    draft: dict,
) -> list[dict[str, str]]:
    language = "Traditional Chinese" if locale == "zh-TW" else "English"
    minimum, length_requirement = article_length_requirement(locale)
    unit = "CJK characters" if locale == "zh-TW" else "English words"
    return [
        {
            "role": "system",
            "content": (
                "You are an independent senior news editor for VoltScope. The draft was written by another agent. "
                "Return strict JSON only. Rewrite the complete story into publication-quality news copy while preserving only "
                "facts in the supplied record. Correct weak leads, generic filler, unsupported implications, poor attribution, "
                "unnatural translation, repetition, and source-like phrasing. Never discuss the review process in the article."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Review and rewrite this {language} draft. Return all keys: title, slug, excerpt, html, text, seo_title, "
                f"seo_description. The article body must contain {length_requirement} in both html and text; the publication gate is "
                f"{minimum} {unit}. Count the body before responding and do not shorten a draft below that gate. "
                "Use descriptive news structure and include one "
                f"source link using the exact URL {candidate.source_url}. Do not invent facts to meet the length target. "
                "For Traditional Chinese, use natural Taiwan news language and translate the meaning of the headline.\n\n"
                f"Factual record: {json.dumps(factual_notes, ensure_ascii=False)}\n\n"
                f"Writer draft: {json.dumps(draft, ensure_ascii=False)}"
            ),
        },
    ]
