import re

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleTag, ArticleTopic, Tag, Topic

TOPIC_RULES = {
    "charging-deals": ("discount", "rebate", "incentive", "coupon", "financing", "0% interest", "\u512a\u60e0", "\u6298\u6263"),
    "charging-station": (
        "charging station",
        "fast charger",
        "supercharger",
        "charging network",
        "infrastructure",
        "\u5145\u96fb\u7ad9",
        "\u5145\u96fb\u6a01",
    ),
    "energy-storage": ("energy storage", "battery energy storage", "bess", "grid-scale battery", "儲能", "電力儲存", "電網級電池"),
    "charging": ("charging", "charger", "battery", "range", "kwh", "cell", "\u5145\u96fb", "\u96fb\u6c60", "\u7e8c\u822a"),
    "smart-mobility": (
        "autonomous",
        "robotaxi",
        "self-driving",
        "driverless",
        "mobility",
        "lidar",
        "fleet",
        "\u81ea\u99d5",
        "\u7121\u4eba\u99d5\u99db",
        "\u667a\u6167\u79fb\u52d5",
    ),
    "energy": (
        "renewable energy",
        "energy transition",
        "power grid",
        "electricity market",
        "solar power",
        "wind power",
        "geothermal",
        "nuclear energy",
        "hydrogen energy",
        "能源科技",
        "再生能源",
        "能源轉型",
        "太陽能",
        "離岸風電",
        "風力發電",
        "地熱",
        "核能",
        "氫能",
        "綠電",
        "電網",
    ),
    "ev": ("electric vehicle", "electric car", " ev ", "tesla", "ford", "rivian", "lucid", "\u96fb\u52d5\u8eca"),
}

TAG_RULES = {
    "battery": ("battery", "cell", "kwh", "\u96fb\u6c60"),
    "charging": ("charging", "charger", "\u5145\u96fb"),
    "charging-deals": ("discount", "rebate", "incentive", "coupon", "financing", "0% interest", "\u512a\u60e0", "\u6298\u6263"),
    "charging-station": (
        "charging station",
        "fast charger",
        "supercharger",
        "charging network",
        "\u5145\u96fb\u7ad9",
        "\u5145\u96fb\u6a01",
    ),
    "energy": ("renewable energy", "energy transition", "power grid", "能源科技", "再生能源", "能源轉型", "綠電", "電網"),
    "energy-storage": ("energy storage", "battery energy storage", "bess", "grid-scale battery", "儲能", "電力儲存", "電網級電池"),
    "ev": ("electric vehicle", "electric car", " ev ", "tesla", "ford", "rivian", "lucid", "\u96fb\u52d5\u8eca"),
    "ev-charging": ("ev charging", "electric vehicle charging", "\u96fb\u52d5\u8eca\u5145\u96fb"),
    "home-energy": ("home energy", "vehicle-to-home", "v2h", "home battery", "\u5bb6\u7528\u5132\u80fd"),
    "policy": (
        "policy",
        "regulation",
        "government",
        "senate",
        "subsidy",
        "tariff",
        "nhtsa",
        "\u653f\u7b56",
        "\u6cd5\u898f",
        "\u653f\u5e9c",
    ),
    "smart-mobility": (
        "autonomous",
        "robotaxi",
        "self-driving",
        "driverless",
        "mobility",
        "lidar",
        "fleet",
        "\u81ea\u99d5",
        "\u7121\u4eba\u99d5\u99db",
        "\u667a\u6167\u79fb\u52d5",
    ),
    "solar": ("solar", "photovoltaic", "pv system", "\u592a\u967d\u80fd", "\u5149\u96fb"),
}


def keyword_matches(text: str, keyword: str) -> int:
    normalized = text.lower()
    candidate = keyword.lower()
    if candidate.strip() != candidate or " " in candidate or not candidate.isascii():
        return normalized.count(candidate)
    return len(re.findall(rf"\b{re.escape(candidate)}\b", normalized))


def score_rules(text: str, rules: dict[str, tuple[str, ...]]) -> dict[str, int]:
    return {slug: sum(keyword_matches(text, keyword) for keyword in keywords) for slug, keywords in rules.items()}


async def classify_generated_article(session: AsyncSession, article_id: str, text: str) -> tuple[str | None, list[str]]:
    topics = (await session.execute(select(Topic))).scalars().all()
    topic_by_slug = {topic.slug: topic for topic in topics}
    topic_scores = score_rules(text, TOPIC_RULES)
    available_topic_scores = {slug: score for slug, score in topic_scores.items() if slug in topic_by_slug}
    primary_topic_slug = max(available_topic_scores, key=available_topic_scores.get) if available_topic_scores else None
    if primary_topic_slug is None or available_topic_scores[primary_topic_slug] == 0:
        primary_topic_slug = "ev" if "ev" in topic_by_slug else next(iter(topic_by_slug), None)

    tags = (await session.execute(select(Tag).where(Tag.is_active.is_(True)))).scalars().all()
    tag_by_slug = {tag.slug: tag for tag in tags}
    tag_scores = score_rules(text, TAG_RULES)
    selected_tag_slugs = [slug for slug, score in tag_scores.items() if score > 0 and slug in tag_by_slug]
    if primary_topic_slug in tag_by_slug and primary_topic_slug not in selected_tag_slugs:
        selected_tag_slugs.append(primary_topic_slug)
    if not selected_tag_slugs and "ev" in tag_by_slug:
        selected_tag_slugs.append("ev")

    await session.execute(delete(ArticleTopic).where(ArticleTopic.article_id == article_id))
    await session.execute(delete(ArticleTag).where(ArticleTag.article_id == article_id))
    if primary_topic_slug:
        session.add(ArticleTopic(article_id=article_id, topic_id=topic_by_slug[primary_topic_slug].id, is_primary=True))
    for slug in selected_tag_slugs:
        session.add(ArticleTag(article_id=article_id, tag_id=tag_by_slug[slug].id))
    return primary_topic_slug, selected_tag_slugs
