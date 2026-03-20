from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

_VK_API = "https://api.vk.com/method"
_VK_VERSION = "5.131"


@dataclass
class VKVideo:
    title: str
    url: str
    group: str
    topic: str
    duration_minutes: int | None = None


class VKClient(BaseIntegration):
    """VK API — поиск видео по запросу."""

    def __init__(self, http_client: httpx.AsyncClient, access_token: str) -> None:
        self._client = http_client
        self._token = access_token

    async def search_videos(
        self, query: str, topic: str, max_results: int = 5
    ) -> list[VKVideo]:
        try:
            resp = await self._client.get(
                f"{_VK_API}/video.search",
                params={
                    "q": query,
                    "count": max_results,
                    "access_token": self._token,
                    "v": _VK_VERSION,
                },
            )
            resp.raise_for_status()
        except Exception:
            logger.exception("VK video search failed: %s", query)
            return []

        items = resp.json().get("response", {}).get("items", [])
        return [
            VKVideo(
                title=item.get("title", ""),
                url=f"https://vk.com/video{item.get('owner_id', 0)}_{item.get('id', 0)}",
                group=str(item.get("owner_id", "")),
                topic=topic,
                duration_minutes=item["duration"] // 60 if item.get("duration") else None,
            )
            for item in items
        ]
