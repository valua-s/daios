from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


@dataclass
class YouTubeVideo:
    title: str
    url: str
    channel: str
    topic: str
    duration_minutes: int | None = None


class YouTubeClient(BaseIntegration):
    """YouTube Data API v3 — поиск по запросу и по каналу."""

    def __init__(self, http_client: httpx.AsyncClient, api_key: str) -> None:
        self._client = http_client
        self._api_key = api_key

    async def search(self, query: str, topic: str, max_results: int = 5) -> list[YouTubeVideo]:
        try:
            resp = await self._client.get(
                _SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": max_results,
                    "key": self._api_key,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("YouTube search failed: %s", query)
            return []

        return [
            YouTubeVideo(
                title=item["snippet"]["title"],
                url=f"https://youtube.com/watch?v={item['id']['videoId']}",
                channel=item["snippet"]["channelTitle"],
                topic=topic,
            )
            for item in resp.json().get("items", [])
        ]

    async def get_channel_videos(
        self, channel_id: str, topic: str, max_results: int = 5
    ) -> list[YouTubeVideo]:
        try:
            resp = await self._client.get(
                _SEARCH_URL,
                params={
                    "part": "snippet",
                    "channelId": channel_id,
                    "type": "video",
                    "order": "date",
                    "maxResults": max_results,
                    "key": self._api_key,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("YouTube channel fetch failed: %s", channel_id)
            return []

        return [
            YouTubeVideo(
                title=item["snippet"]["title"],
                url=f"https://youtube.com/watch?v={item['id']['videoId']}",
                channel=item["snippet"]["channelTitle"],
                topic=topic,
            )
            for item in resp.json().get("items", [])
        ]
