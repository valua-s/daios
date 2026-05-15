from __future__ import annotations

import logging
import time

import httpx
from redis.asyncio import Redis

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://www.strava.com/api/v3/oauth/token"
ACTIVITY_URL = "https://www.strava.com/api/v3/activities/{id}"
ACCESS_TOKEN_CACHE_KEY = "daios:strava:access_token"

RUNNING_TYPES = {"Run", "TrailRun", "VirtualRun"}


class StravaAuthError(RuntimeError):
    """Не удалось обновить access token."""


class StravaClient(BaseIntegration):
    """Клиент Strava API: ленивый refresh access_token + чтение активностей."""

    def __init__(self, http_client: httpx.AsyncClient, redis: Redis) -> None:
        self._http = http_client
        self._redis = redis

    async def _get_access_token(self) -> str:
        cached = await self._redis.get(ACCESS_TOKEN_CACHE_KEY)
        if cached:
            return cached
        return await self._refresh_access_token()

    async def _refresh_access_token(self) -> str:
        response = await self._http.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret.get_secret_value(),
                "grant_type": "refresh_token",
                "refresh_token": settings.strava_refresh_token.get_secret_value(),
            },
        )
        if response.status_code != 200:
            logger.error("Strava token refresh failed: %s %s", response.status_code, response.text)
            raise StravaAuthError(f"Strava token refresh failed: {response.status_code}")

        data = response.json()
        access_token: str = data["access_token"]
        expires_at: int = int(data["expires_at"])

        ttl = max(60, expires_at - int(time.time()) - 60)
        await self._redis.set(ACCESS_TOKEN_CACHE_KEY, access_token, ex=ttl)
        return access_token

    async def fetch_activity(self, activity_id: int) -> dict:
        token = await self._get_access_token()
        response = await self._http.get(
            ACTIVITY_URL.format(id=activity_id),
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401:
            token = await self._refresh_access_token()
            response = await self._http.get(
                ACTIVITY_URL.format(id=activity_id),
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def is_running(activity_type: str) -> bool:
        return activity_type in RUNNING_TYPES
