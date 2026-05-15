from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.integrations.strava import StravaClient
from backend.repositories.completed_workout_repo import CompletedWorkoutRepository

logger = logging.getLogger(__name__)


@dataclass
class StravaWebhookEvent:
    object_type: str       # "activity" | "athlete"
    object_id: int         # activity_id
    aspect_type: str       # "create" | "update" | "delete"
    owner_id: int
    event_time: int


@dataclass
class WeeklyKmDTO:
    planned_km: float
    actual_km: float
    percent: int


class StravaService:
    def __init__(
        self,
        session: AsyncSession,
        repo: CompletedWorkoutRepository,
        client: StravaClient,
    ) -> None:
        self._session = session
        self._repo = repo
        self._client = client

    async def handle_webhook_event(self, event: StravaWebhookEvent) -> None:
        if event.object_type != "activity":
            return

        if event.aspect_type == "delete":
            deleted = await self._repo.delete_by_strava_id(event.object_id)
            if deleted:
                await self._session.commit()
                logger.info("Deleted completed workout strava_id=%s", event.object_id)
            return

        if event.aspect_type not in {"create", "update"}:
            return

        try:
            payload = await self._client.fetch_activity(event.object_id)
        except Exception:
            logger.exception("Failed to fetch Strava activity %s", event.object_id)
            return

        activity_type = str(payload.get("type", ""))
        if not StravaClient.is_running(activity_type):
            logger.info(
                "Skipping non-running Strava activity %s (type=%s)",
                event.object_id, activity_type,
            )
            return

        await self._repo.upsert_from_strava(payload)
        await self._session.commit()
        logger.info("Upserted completed workout strava_id=%s type=%s", event.object_id, activity_type)

    async def set_distance_override(
        self, completed_id: int, distance_km: float | None,
    ) -> bool:
        updated = await self._repo.update_distance_override(completed_id, distance_km)
        if updated is None:
            return False
        await self._session.commit()
        return True

    async def weekly_running_summary(
        self, week_start: date, week_end: date, planned_km: float,
    ) -> WeeklyKmDTO:
        records = await self._repo.get_week(week_start, week_end)
        actual = round(sum(r.effective_distance_km for r in records), 2)
        percent = int(round(actual / planned_km * 100)) if planned_km > 0 else 0
        return WeeklyKmDTO(planned_km=round(planned_km, 2), actual_km=actual, percent=percent)
