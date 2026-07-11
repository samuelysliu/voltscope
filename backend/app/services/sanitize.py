import bleach

ALLOWED_TAGS = [
    "a",
    "blockquote",
    "br",
    "code",
    "em",
    "figcaption",
    "figure",
    "h2",
    "h3",
    "hr",
    "img",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "u",
    "ul",
]
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title", "rel", "target"],
    "img": ["src", "alt", "width", "height", "loading"],
    "th": ["scope"],
}
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def sanitize_html(html: str) -> str:
    cleaned = bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, protocols=ALLOWED_PROTOCOLS, strip=True)
    return bleach.linkify(cleaned, callbacks=[nofollow])


def nofollow(attrs: dict, new: bool = False) -> dict:
    href_key = (None, "href")
    if href_key in attrs:
        attrs[(None, "rel")] = "nofollow sponsored noopener"
    return attrs

