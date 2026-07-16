import asyncio
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models import SourceParserVersion, SourceWhitelist


def domain_from_url(value: str) -> str:
    parsed = urlparse(value)
    domain = (parsed.netloc or parsed.path).lower().split("@")[-1].split(":")[0]
    return domain[4:] if domain.startswith("www.") else domain


DEFAULT_SOURCES = [
    {
        "name": "Yahoo Taiwan Autos EV",
        "homepage_url": "https://autos.yahoo.com.tw",
        "list_url": "https://autos.yahoo.com.tw/car-topics/EV-and-Hybrid",
        "rss_url": None,
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "charging-station", "charging-deals"],
        "crawl_method": "html",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
        "enabled": False,
        "force_disabled": True,
    },
    {
        "name": "U-CAR EV News",
        "homepage_url": "https://www.u-car.com.tw",
        "list_url": "https://www.u-car.com.tw/news",
        "rss_url": None,
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "smart-mobility"],
        "crawl_method": "html",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "PTS Taiwan EV News",
        "homepage_url": "https://news.pts.org.tw",
        "list_url": "https://news.pts.org.tw/tag/3735/",
        "rss_url": None,
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "high",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "html",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "TechNews Automotive Technology",
        "homepage_url": "https://technews.tw",
        "list_url": "https://technews.tw/category/car-tech/",
        "rss_url": "https://technews.tw/category/car-tech/feed/",
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "InsideEVs",
        "homepage_url": "https://insideevs.com",
        "list_url": "https://insideevs.com/news/",
        "rss_url": "https://insideevs.com/rss/news/all/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "high",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "Electrek",
        "homepage_url": "https://electrek.co",
        "list_url": "https://electrek.co/guides/electric-vehicles/",
        "rss_url": "https://electrek.co/feed/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "high",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "InsideEVs Charging",
        "homepage_url": "https://insideevs.com",
        "list_url": "https://insideevs.com/news/charging/",
        "rss_url": "https://insideevs.com/rss/category/charging/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "high",
        "allowed_topics": ["charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "Charged EVs",
        "homepage_url": "https://chargedevs.com",
        "list_url": "https://chargedevs.com/category/newswire/",
        "rss_url": "https://chargedevs.com/feed/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "high",
        "allowed_topics": ["ev", "charging", "charging-station", "battery"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "The Driven",
        "homepage_url": "https://thedriven.io",
        "list_url": "https://thedriven.io/category/ev-news/",
        "rss_url": "https://thedriven.io/feed/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "CleanTechnica EV Charging",
        "homepage_url": "https://cleantechnica.com",
        "list_url": "https://cleantechnica.com/category/clean-transport-2/electric-vehicles/",
        "rss_url": "https://cleantechnica.com/feed/",
        "source_group": "international_media",
        "region": "international",
        "default_language": "en",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "charging-station", "smart-mobility"],
        "crawl_method": "rss",
        "quota_role": "international_daily",
        "allow_auto_publish": True,
        "requires_review": False,
    },
    {
        "name": "EVOASIS News",
        "homepage_url": "https://www.evoasis.com.tw",
        "list_url": "https://www.evoasis.com.tw/latestnews/list",
        "rss_url": None,
        "source_group": "charging_operator",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "high",
        "allowed_topics": ["charging", "charging-station", "charging-deals"],
        "crawl_method": "html",
        "quota_role": "event_driven",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "U-POWER News",
        "homepage_url": "https://www.u-power.com.tw",
        "list_url": "https://www.u-power.com.tw/news.html",
        "rss_url": None,
        "source_group": "charging_operator",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "high",
        "allowed_topics": ["charging", "charging-station", "charging-deals"],
        "crawl_method": "html",
        "quota_role": "event_driven",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "TAIL News",
        "homepage_url": "https://www.evtail.com.tw",
        "list_url": "https://www.evtail.com.tw/posts/list/news",
        "rss_url": None,
        "source_group": "charging_operator",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "high",
        "allowed_topics": ["charging", "charging-station", "charging-deals", "energy"],
        "crawl_method": "html",
        "quota_role": "event_driven",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "Battway EV News",
        "homepage_url": "https://www.battway.com.tw",
        "list_url": "https://www.battway.com.tw/",
        "rss_url": None,
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["ev", "charging", "charging-station", "charging-deals", "energy"],
        "crawl_method": "html",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "TechNews Energy",
        "homepage_url": "https://technews.tw",
        "list_url": "https://technews.tw/category/%E8%83%BD%E6%BA%90%E7%A7%91%E6%8A%80/",
        "rss_url": "https://technews.tw/category/%E8%83%BD%E6%BA%90%E7%A7%91%E6%8A%80/feed/",
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["energy", "energy-storage"],
        "crawl_method": "rss",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
    {
        "name": "TechNews Energy Storage",
        "homepage_url": "https://technews.tw",
        "list_url": "https://technews.tw/category/%E8%83%BD%E6%BA%90%E7%A7%91%E6%8A%80/%E9%9B%BB%E5%8A%9B%E5%84%B2%E5%AD%98/",
        "rss_url": "https://technews.tw/category/%E8%83%BD%E6%BA%90%E7%A7%91%E6%8A%80/%E9%9B%BB%E5%8A%9B%E5%84%B2%E5%AD%98/feed/",
        "source_group": "taiwan_media",
        "region": "taiwan",
        "default_language": "zh",
        "trust_level": "medium",
        "allowed_topics": ["energy-storage", "energy", "battery"],
        "crawl_method": "rss",
        "quota_role": "taiwan_daily",
        "allow_auto_publish": False,
        "requires_review": True,
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        for item in DEFAULT_SOURCES:
            domain = domain_from_url(item["homepage_url"])
            source = await session.scalar(
                select(SourceWhitelist).where(
                    SourceWhitelist.domain == domain,
                    SourceWhitelist.name == item["name"],
                )
            )
            is_new = source is None
            if is_new:
                source = SourceWhitelist(
                    name=item["name"],
                    homepage_url=item["homepage_url"],
                    domain=domain,
                    source_group=item["source_group"],
                    region=item["region"],
                    created_at=datetime.now(UTC),
                    updated_at=datetime.now(UTC),
                    enabled=item.get("enabled", True),
                )
                session.add(source)
                await session.flush()
            source.list_url = item["list_url"]
            source.rss_url = item["rss_url"]
            source.default_language = item["default_language"]
            source.trust_level = item["trust_level"]
            if item.get("force_disabled"):
                source.enabled = False
            source.allowed_topics = item["allowed_topics"]
            source.crawl_method = item["crawl_method"]
            source.quota_role = item["quota_role"]
            source.allow_auto_publish = item["allow_auto_publish"]
            source.requires_review = item["requires_review"]
            if is_new:
                source.health_status = "healthy" if source.enabled else "disabled"
            elif not source.enabled:
                source.health_status = "disabled"
            elif source.health_status == "disabled":
                source.health_status = "healthy"

            version = await session.scalar(
                select(SourceParserVersion).where(SourceParserVersion.source_id == source.id, SourceParserVersion.version == 1)
            )
            if version is None:
                version = SourceParserVersion(
                    source_id=source.id,
                    version=1,
                    parser_type="rss" if item["rss_url"] else item["crawl_method"],
                    created_by="system",
                    created_at=datetime.now(UTC),
                )
                session.add(version)
            version.selector_config = {
                "rss_url": item["rss_url"],
                "list_url": item["list_url"],
                "homepage_url": item["homepage_url"],
            }
            version.sample_url = item["rss_url"] or item["list_url"] or item["homepage_url"]
            version.confidence_score = 1.0 if item["rss_url"] else 0.8
            version.validation_status = "approved" if source.enabled else "retired"
            version.is_active = source.enabled
            version.approved_at = datetime.now(UTC) if source.enabled else None
            version.retired_at = None if source.enabled else datetime.now(UTC)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
