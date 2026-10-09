"""Extract canonical Instagram references without fetching anything."""

import html
import json
import re
from urllib.parse import urlparse

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_-]+/?", re.I
)


def canonical_url(value: str) -> str:
    parsed = urlparse(value.strip())
    match = re.fullmatch(r"/(reel|reels|p|tv)/([A-Za-z0-9_-]+)/?", parsed.path)
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.hostname not in {"instagram.com", "www.instagram.com"}
        or not match
    ):
        raise ValueError("Use an Instagram reel or post URL.")
    kind = "reel" if match[1] in {"reel", "reels", "tv"} else "p"
    return f"https://www.instagram.com/{kind}/{match[2]}/"


def parse_import(text: str) -> list[dict]:
    found: dict[str, set[str]] = {}

    def add(value, collection=""):
        for match in URL_PATTERN.finditer(html.unescape(value)):
            url = canonical_url(match[0])
            found.setdefault(url, set())
            if collection.strip():
                found[url].add(collection.strip()[:100])

    def walk(value):
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str):
            add(value)

    try:
        walk(json.loads(text))
    except json.JSONDecodeError:
        for line in text.splitlines():
            parts = line.split("\t", 1)
            add(parts[0], parts[1] if len(parts) > 1 else "")
    return [{"url": url, "collections": sorted(collections)} for url, collections in found.items()]
