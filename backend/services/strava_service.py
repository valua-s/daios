from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.core.config import settings
from backend.integrations.strava import map_activity_type

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.integrations.strava import StravaClient
    from backend.repositories.completed_workout_repo import (
        CompletedWorkoutRepository,
    )

logger = logging.getLogger(__name__)

_tz = ZoneInfo(settings.app_timezone)
_SECONDS_PER_MINUTE = 60
_METERS_PER_KM = 1000


class StravaService:
    """Периодический опрос Strava: активности за последние дни → факт тренировок.

    Дни с ручной отметкой не трогаются — ручной ввод приоритетнее.
    """

    def __init__(
        self,
        session: AsyncSession,
        repo: CompletedWorkoutRepository,
        client: StravaClient,
    ) -> None:
        self._session = session
        self._repo = repo
        self._client = client

    async def sync_recent(self, days: int | None = None) -> int:
        if not settings.strava_enabled:
            logger.info("Strava sync skipped: credentials are not configured")
            return 0

        window_days = days if days is not None else settings.strava_sync_days
        now = datetime.now(tz=_tz)
        after = now - timedelta(days=window_days)

        activities = await self._client.list_activities(after, now)
        manual_keys = await self._repo.get_manual_keys(after.date(), now.date())

        saved = 0
        for activity in activities:
            if await self._store(activity, manual_keys):
                saved += 1

        removed = await self._repo.delete_strava_for_keys(manual_keys)
        await self._session.commit()
        logger.info(
            "Strava sync done: %d activities saved, %d superseded by manual entries",
            saved, removed,
        )
        return saved

    async def _store(self, activity: dict, manual_keys: set[tuple[date, str]]) -> bool:
        activity_type = map_activity_type(str(activity.get("sport_type") or activity.get("type") or ""))
        if activity_type is None:
            return False

        started_at = _parse_started_at(activity.get("start_date_local"))
        if started_at is None:
            logger.warning("Strava activity %s has no start date, skipped", activity.get("id"))
            return False

        if (started_at.date(), activity_type) in manual_keys:
            return False

        await self._repo.upsert_from_strava(
            strava_activity_id=int(activity["id"]),
            workout_date=started_at.date(),
            activity_type=activity_type,
            distance_km=round(float(activity.get("distance") or 0) / _METERS_PER_KM, 3),
            duration_minutes=round(float(activity.get("moving_time") or 0) / _SECONDS_PER_MINUTE),
            started_at=started_at,
            note=activity.get("name"),
        )
        return True


def _parse_started_at(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "")).replace(tzinfo=None)
    except ValueError:
        return None
