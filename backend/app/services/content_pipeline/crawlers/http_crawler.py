import httpx
from urllib.parse import urlsplit

from app.core.config import get_settings


DEFAULT_HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9,zh-TW;q=0.8",
    "cache-control": "no-cache",
}


async def fetch_text(url: str) -> tuple[str, str]:
    settings = get_settings()
    timeout = httpx.Timeout(float(settings.content_pipeline_crawler_timeout_seconds))
    parsed = urlsplit(url)
    headers = {**DEFAULT_HEADERS, "referer": f"{parsed.scheme}://{parsed.netloc}/"}
    async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text, str(response.url)
