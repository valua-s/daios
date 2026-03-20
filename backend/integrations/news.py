from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx

from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

_EVERYTHING_URL = "https://newsapi.org/v2/everything"


@dataclass
class NewsArticle:
    title: str
    url: str
    summary: str
    source: str
    topic: str
    published_at: datetime | None


class NewsClient(BaseIntegration):
    """NewsAPI — поиск статей по запросу."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._client = http_client
        self._api_key = api_key

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        try:
            resp = await self._client.get(
                _EVERYTHING_URL,
                params={
                    "q": query,
                    "pageSize": max_results,
                    "language": "ru",
                    "sortBy": "publishedAt",
                    "apiKey": self._api_key,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("NewsAPI search failed: %s", query)
            return []

        articles: list[NewsArticle] = []
        for item in resp.json().get("articles", []):
            published_at: datetime | None = None
            if raw := item.get("publishedAt"):
                try:
                    published_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                except Exception:
                    pass

            articles.append(
                NewsArticle(
                    title=item.get("title") or "",
                    url=item.get("url") or "",
                    summary=(item.get("description") or "")[:500].strip(),
                    source=item.get("source", {}).get("name") or "",
                    topic=topic,
                    published_at=published_at,
                )
            )

        return articles
