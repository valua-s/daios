from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

_EVERYTHING_URL = "https://newsapi.org/v2/everything"
_HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
_HN_ITEM_URL = "https://news.ycombinator.com/item?id="
_NEWSDATA_URL = "https://newsdata.io/api/1/latest"
_GNEWS_URL = "https://gnews.io/api/v4/search"
_CURRENTS_URL = "https://api.currentsapi.services/v1/search"
_FREENEWS_URL = "https://api.freenewsapi.io/v1/news"
_FREENEWS_DETAILS_URL = "https://api.freenewsapi.io/v1/details"

_NEWSDATA_MAX_SIZE = 10
_SUMMARY_LIMIT = 500
_FRESH_HOURS = 24
_TOO_MANY_REQUESTS = 429
_RETRY_DELAY_SECONDS = 1.0

_FREENEWS_TOPICS = {
    "python": "technology",
    "ai": "technology",
    "running": "sports",
    "economics": "economy",
    "politics": "politics",
}
_FREENEWS_FALLBACK_TOPIC = "world"
_FREENEWS_DETAILS_LIMIT = 3


@dataclass
class NewsArticle:
    title: str
    url: str
    summary: str
    source: str
    topic: str
    published_at: datetime | None


def _parse_published(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _clean(text: str | None) -> str:
    return (text or "")[:_SUMMARY_LIMIT].strip()


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

        return [
            NewsArticle(
                title=item.get("title") or "",
                url=item.get("url") or "",
                summary=_clean(item.get("description")),
                source=item.get("source", {}).get("name") or "",
                topic=topic,
                published_at=_parse_published(item.get("publishedAt")),
            )
            for item in resp.json().get("articles", [])
        ]


class NewsProvider(BaseIntegration):
    """Общий контракт поставщика новостей для дайджеста."""

    name = "provider"

    def __init__(self, http_client: httpx.AsyncClient, api_key: str = "") -> None:
        self._client = http_client
        self._api_key = api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key)

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        raise NotImplementedError

    async def _get(
        self,
        url: str,
        params: dict,
        headers: dict[str, str] | None = None,
        *,
        retry: bool = True,
    ) -> dict:
        if not self.enabled:
            return {}
        try:
            resp = await self._client.get(url, params=params, headers=headers)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == _TOO_MANY_REQUESTS and retry:
                await asyncio.sleep(_RETRY_DELAY_SECONDS)
                return await self._get(url, params, headers, retry=False)
            logger.warning("%s request failed: HTTP %s", self.name, exc.response.status_code)
            return {}
        except Exception as exc:
            logger.warning("%s request failed: %s", self.name, type(exc).__name__)
            return {}
        payload = resp.json()
        return payload if isinstance(payload, dict) else {"data": payload}


class HackerNewsProvider(NewsProvider):
    """Hacker News через Algolia — без ключа и лимитов."""

    name = "hackernews"

    @property
    def enabled(self) -> bool:
        return True

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        since = datetime.now(tz=UTC) - timedelta(hours=_FRESH_HOURS)
        payload = await self._get(
            _HN_SEARCH_URL,
            {
                "query": query,
                "tags": "story",
                "hitsPerPage": max_results,
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
            },
        )
        return [
            NewsArticle(
                title=hit.get("title") or hit.get("story_title") or "",
                url=hit.get("url") or f"{_HN_ITEM_URL}{hit.get('objectID', '')}",
                summary=_clean(hit.get("story_text")),
                source=f"Hacker News ({hit.get('points') or 0} points)",
                topic=topic,
                published_at=_parse_published(hit.get("created_at")),
            )
            for hit in payload.get("hits", [])
        ]


class NewsDataProvider(NewsProvider):
    """NewsData.io — latest endpoint с фильтром по языку."""

    name = "newsdata"

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        payload = await self._get(
            _NEWSDATA_URL,
            {
                "apikey": self._api_key,
                "q": query,
                "language": "en",
                "size": min(max_results, _NEWSDATA_MAX_SIZE),
            },
        )
        return [
            NewsArticle(
                title=item.get("title") or "",
                url=item.get("link") or "",
                summary=_clean(item.get("description")),
                source=item.get("source_id") or "",
                topic=topic,
                published_at=_parse_published(item.get("pubDate")),
            )
            for item in payload.get("results", [])
        ]


class GNewsProvider(NewsProvider):
    """GNews — поиск по ключевым словам."""

    name = "gnews"

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        payload = await self._get(
            _GNEWS_URL,
            {
                "q": query,
                "lang": "en",
                "max": max_results,
                "apikey": self._api_key,
            },
        )
        return [
            NewsArticle(
                title=item.get("title") or "",
                url=item.get("url") or "",
                summary=_clean(item.get("description")),
                source=(item.get("source") or {}).get("name") or "",
                topic=topic,
                published_at=_parse_published(item.get("publishedAt")),
            )
            for item in payload.get("articles", [])
        ]


class CurrentsProvider(NewsProvider):
    """Currents API — ключ передаётся заголовком Authorization."""

    name = "currents"

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:
        payload = await self._get(
            _CURRENTS_URL,
            {"keywords": query, "language": "en"},
            {"Authorization": self._api_key},
        )
        return [
            NewsArticle(
                title=item.get("title") or "",
                url=item.get("url") or "",
                summary=_clean(item.get("description")),
                source=item.get("author") or "Currents",
                topic=topic,
                published_at=_parse_published(item.get("published")),
            )
            for item in payload.get("news", [])[:max_results]
        ]


class FreeNewsProvider(NewsProvider):
    """FreeNewsApi.io — ключ передаётся заголовком x-api-key.

    Список отдаёт только заголовки, ссылка и текст доступны в /v1/details по uuid.
    Поиск по ключевым словам у API отвечает 500, поэтому берём фильтр по теме.
    """

    name = "freenews"

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[NewsArticle]:  # noqa: ARG002
        since = datetime.now(tz=UTC) - timedelta(hours=_FRESH_HOURS)
        payload = await self._get(
            _FREENEWS_URL,
            {
                "language": "en",
                "topic": _FREENEWS_TOPICS.get(topic, _FREENEWS_FALLBACK_TOPIC),
                "published_after": since.date().isoformat(),
            },
            {"x-api-key": self._api_key},
        )
        limit = min(max_results, _FREENEWS_DETAILS_LIMIT)
        articles = []
        for item in payload.get("data", [])[:limit]:
            article = await self._details(item.get("uuid") or "", topic)
            if article is not None:
                articles.append(article)
        return articles

    async def _details(self, uuid: str, topic: str) -> NewsArticle | None:
        if not uuid:
            return None
        payload = await self._get(
            _FREENEWS_DETAILS_URL, {"uuid": uuid}, {"x-api-key": self._api_key},
        )
        data = payload.get("data") or payload
        title = data.get("title") or ""
        url = data.get("original_url") or ""
        if not title or not url:
            return None
        publisher = data.get("publisher")
        return NewsArticle(
            title=title,
            url=url,
            summary=_clean(data.get("incipit") or data.get("body")),
            source=publisher.get("name", "") if isinstance(publisher, dict) else str(publisher or ""),
            topic=topic,
            published_at=_parse_published(data.get("published_at")),
        )
