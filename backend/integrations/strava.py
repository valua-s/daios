from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import httpx
from redis.asyncio import Redis

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

OAUTH_URL = "https://www.strava.com/api/v3/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
AUTH_CACHE_KEY = "daios:strava:access_token"

PER_PAGE = 100
TOKEN_EXPIRY_MARGIN_SECONDS = 60

_AUTH_RETRY_STATUSES = (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN)

RUNNING = "running"
CYCLING = "cycling"
SWIMMING = "swimming"
STRENGTH = "strength"

ACTIVITY_TYPE_MAP: dict[str, str] = {
    "Run": RUNNING,
    "TrailRun": RUNNING,
    "VirtualRun": RUNNING,
    "Ride": CYCLING,
    "VirtualRide": CYCLING,
    "GravelRide": CYCLING,
    "MountainBikeRide": CYCLING,
    "EBikeRide": CYCLING,
    "Swim": SWIMMING,
    "WeightTraining": STRENGTH,
    "Workout": STRENGTH,
    "Crossfit": STRENGTH,
}


class StravaAuthError(RuntimeError):
    """Не удалось обновить access token."""


def build_http_client() -> httpx.AsyncClient:
    """Отдельный клиент: Strava опрашивается через прокси, остальные API — напрямую."""
    proxy = settings.strava_proxy_url or None
    return httpx.AsyncClient(timeout=30.0, proxy=proxy)


def map_activity_type(strava_type: str) -> str | None:
    """Тип активности Strava → тип тренировки в плане. None — тип не учитываем."""
    return ACTIVITY_TYPE_MAP.get(strava_type)


class StravaClient(BaseIntegration):
    """Клиент Strava API: ленивый refresh access_token + чтение списка активностей."""

    def __init__(self, http_client: httpx.AsyncClient, redis: Redis) -> None:
        self._http = http_client
        self._redis = redis

    async def list_activities(self, after: datetime, before: datetime) -> list[dict]:
        """Активности атлета в интервале, от старых к новым."""
        token = await self._get_access_token()
        params = {
            "after": int(after.timestamp()),
            "before": int(before.timestamp()),
            "per_page": PER_PAGE,
        }
        response = await self._http.get(
            ACTIVITIES_URL,
            params=params,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == httpx.codes.UNAUTHORIZED:
            logger.warning("Strava rejected access token, refreshing: %s", response.text[:300])
            await self._redis.delete(AUTH_CACHE_KEY)
            token = await self._refresh_access_token()
            response = await self._http.get(
                ACTIVITIES_URL,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
            )
        if response.status_code == httpx.codes.FORBIDDEN:
            msg = f"Strava отклонила запрос активностей (403): {response.text[:300]}"
            raise StravaAuthError(msg)
        response.raise_for_status()
        activities: list[dict] = response.json()
        return sorted(activities, key=lambda a: str(a.get("start_date_local", "")))

    async def _get_access_token(self) -> str:
        cached = await self._redis.get(AUTH_CACHE_KEY)
        if cached:
            return cached
        return await self._refresh_access_token()

    async def _refresh_access_token(self) -> str:
        response = await self._http.post(
            OAUTH_URL,
            data={
                "client_id": settings.strava_client_id,
                "client_secret": settings.strava_client_secret.get_secret_value(),
                "grant_type": "refresh_token",
                "refresh_token": settings.strava_refresh_token.get_secret_value(),
            },
        )
        if response.status_code != httpx.codes.OK:
            logger.error("Strava token refresh failed: %s %s", response.status_code, response.text)
            msg = f"Strava token refresh failed: {response.status_code}"
            raise StravaAuthError(msg)

        data = response.json()
        new_refresh: str = data.get("refresh_token", "")
        if new_refresh and new_refresh != settings.strava_refresh_token.get_secret_value():
            logger.warning(
                "Strava выдала новый refresh_token — обнови STRAVA_REFRESH_TOKEN в .env: %s",
                new_refresh,
            )
        access_token: str = data["access_token"]
        expires_at = int(data["expires_at"])

        ttl = max(
            TOKEN_EXPIRY_MARGIN_SECONDS,
            expires_at - int(time.time()) - TOKEN_EXPIRY_MARGIN_SECONDS,
        )
        await self._redis.set(AUTH_CACHE_KEY, access_token, ex=ttl)
        return access_token
