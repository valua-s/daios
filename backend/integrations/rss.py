from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

import feedparser

from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    title: str
    url: str
    summary: str
    topic: str
    source: str
    published_at: datetime | None


class RSSParser(BaseIntegration):
    """Парсит RSS-ленты и возвращает статьи по топику."""

    @staticmethod
    async def fetch(feed_url: str, topic: str, max_items: int = 5) -> list[RSSItem]:
        try:
            feed = await asyncio.to_thread(feedparser.parse, feed_url)
        except Exception:
            logger.exception("RSS fetch failed: %s", feed_url)
            return []

        items: list[RSSItem] = []
        for entry in feed.entries[:max_items]:
            published_at: datetime | None = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6], tzinfo=UTC)
                except Exception:
                    pass

            items.append(RSSItem(
                title=entry.get("title", "").strip(),
                url=entry.get("link", ""),
                summary=entry.get("summary", "")[:500].strip(),
                topic=topic,
                source=feed.feed.get("title", feed_url),
                published_at=published_at,
            ))

        return items
