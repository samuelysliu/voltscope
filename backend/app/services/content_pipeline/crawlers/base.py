from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse


@dataclass
class CrawledCandidate:
    source_url: str
    title: str
    excerpt: str | None = None
    published_at: datetime | None = None
    author: str | None = None
    parser_type: str = "unknown"
    confidence_score: float | None = None


@dataclass
class CrawlResult:
    candidates: list[CrawledCandidate] = field(default_factory=list)
    fallback_used: dict = field(default_factory=dict)
    error_message: str | None = None


def normalize_domain(value: str) -> str:
    parsed = urlparse(value)
    domain = (parsed.netloc or parsed.path).lower().split("@")[-1].split(":")[0]
    return domain[4:] if domain.startswith("www.") else domain


def is_allowed_url(url: str, allowed_domain: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    domain = normalize_domain(url)
    return domain == allowed_domain or domain.endswith(f".{allowed_domain}")


def absolute_allowed_url(url: str, base_url: str, allowed_domain: str) -> str | None:
    absolute = urljoin(base_url, url.strip())
    return absolute if is_allowed_url(absolute, allowed_domain) else None
