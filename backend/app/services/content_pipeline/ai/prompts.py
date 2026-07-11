import json

from app.models import ContentCandidate


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
                "'Ford \u53ec\u56de 4.3 \u842c\u8f1b Mustang Mach-E\uff0c\u5dee\u901f\u5668\u7570\u5e38\u6050\u767c\u51fa\u7206\u88c2\u8072', not the English title plus Chinese filler."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Write a {language} article. Return JSON with keys: title, slug, excerpt, html, text, "
                "seo_title, seo_description. Use p, h2, and a tags in HTML. Include one source link using the exact source_url. "
                "The text field must contain at least 650 CJK characters for zh-TW or at least 520 English words. "
                "Treat anything shorter as invalid, but never invent facts to reach length. "
                "Open with the most newsworthy verified event and its concrete scale or consequence. Follow with evidence, "
                "chronology, technical or regulatory context explicitly present in the notes, affected stakeholders, and the official response. "
                "Use descriptive h2 headings only when they improve a long article; never use generic headings such as Report Highlights, "
                "Industry Context, Taiwan Relevance, or What to Watch. Omit Taiwan entirely unless the factual notes establish a direct connection. "
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
) -> list[dict[str, str]]:
    language = "Traditional Chinese" if locale == "zh-TW" else "English"
    length_requirement = "650-1000 CJK characters" if locale == "zh-TW" else "520-800 words"
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
                f"The text field must contain {length_requirement}; count it before responding. Use p, h2, and a tags in HTML, "
                f"and include the exact source URL {candidate.source_url}. For Traditional Chinese, the headline must state the event "
                "in natural Taiwan news language rather than retaining the English source headline. Do not mention the editing process, "
                "missing context, or Taiwan unless the facts directly involve Taiwan.\n\n"
                f"Failed checks: {json.dumps(issue_codes)}\n\n"
                f"Factual record: {json.dumps(factual_notes, ensure_ascii=False)}\n\n"
                f"Draft to rewrite: {json.dumps(draft, ensure_ascii=False)}"
            ),
        },
    ]
