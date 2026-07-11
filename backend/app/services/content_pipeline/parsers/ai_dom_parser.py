from html import unescape
from html.parser import HTMLParser
import re


class SanitizedDomParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lower = tag.lower()
        if lower in {"script", "style", "noscript", "iframe", "svg"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        safe_attrs = []
        for key, value in attrs:
            if value is None or key.lower().startswith("on"):
                continue
            if key.lower() in {"href", "src", "class", "id", "rel", "type"}:
                safe_attrs.append(f'{key}="{unescape(value)[:240]}"')
        suffix = f" {' '.join(safe_attrs)}" if safe_attrs else ""
        self.parts.append(f"<{lower}{suffix}>")

    def handle_endtag(self, tag: str) -> None:
        lower = tag.lower()
        if lower in {"script", "style", "noscript", "iframe", "svg"}:
            self.skip_depth = max(0, self.skip_depth - 1)
            return
        if not self.skip_depth:
            self.parts.append(f"</{lower}>")

    def handle_data(self, data: str) -> None:
        if not self.skip_depth:
            text = " ".join(data.split())
            if text:
                self.parts.append(unescape(text))


def sanitize_dom_sample(raw_html: str, max_chars: int = 8000) -> str:
    parser = SanitizedDomParser()
    parser.feed(raw_html)
    sample = " ".join(parser.parts)
    sample = re.sub(r"\s+", " ", sample).strip()
    return sample[:max_chars]
