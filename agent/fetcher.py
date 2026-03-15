"""Fetch content from RSS feeds."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from agent.models import ContentItem

logger = logging.getLogger(__name__)


def fetch_rss_feed(url: str, source_label: str) -> list[ContentItem]:
    """Parse a single RSS feed URL into ContentItems."""
    feed = feedparser.parse(url)

    if feed.bozo and not feed.entries:
        logger.warning("Failed to parse feed %s: %s", url, feed.bozo_exception)
        return []

    items = []
    for entry in feed.entries:
        published = _parse_date(entry.get("published_parsed"))
        # Use description/summary for body; strip HTML tags roughly
        body = _strip_html(entry.get("summary", entry.get("description", "")))

        item = ContentItem(
            title=entry.get("title", "(no title)"),
            body=body,
            url=entry.get("link", ""),
            source=source_label,
            author=_extract_author(entry),
            published=published,
            tags=[t.get("term", "") for t in entry.get("tags", [])],
            discussion_url=entry.get("comments", ""),
        )
        items.append(item)

    logger.info("Fetched %d items from %s", len(items), source_label)
    return items


def fetch_all_feeds(
    feed_configs: list[dict[str, Any]],
    source_prefix: str = "nyt",
) -> list[ContentItem]:
    """Fetch all configured RSS feeds and return combined items."""
    all_items: list[ContentItem] = []

    for feed_cfg in feed_configs:
        section = feed_cfg["section"]
        url = feed_cfg["url"]
        source_label = f"{source_prefix}/{section}"

        try:
            items = fetch_rss_feed(url, source_label)
            all_items.extend(items)
        except Exception:
            logger.exception("Error fetching %s", source_label)

    # Deduplicate by URL (articles can appear in multiple sections)
    seen_urls: set[str] = set()
    unique_items: list[ContentItem] = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            unique_items.append(item)

    logger.info("Total unique items after dedup: %d", len(unique_items))
    return unique_items


def _parse_date(time_struct) -> datetime | None:
    """Convert feedparser time struct to datetime."""
    if time_struct is None:
        return None
    try:
        from time import mktime
        return datetime.fromtimestamp(mktime(time_struct), tz=timezone.utc)
    except Exception:
        return None


def _extract_author(entry: dict) -> str:
    """Pull author name from various RSS author fields."""
    if "author" in entry:
        return entry["author"]
    if "authors" in entry and entry["authors"]:
        return ", ".join(a.get("name", "") for a in entry["authors"] if a.get("name"))
    return ""


def _strip_html(text: str) -> str:
    """Rough HTML tag removal. Good enough for RSS snippets."""
    import re
    clean = re.sub(r"<[^>]+>", "", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean
