from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from backend.models.completed_workout import CompletedWorkout
from backend.repositories.base import BaseRepository


class CompletedWorkoutRepository(BaseRepository[CompletedWorkout]):
    model = CompletedWorkout

    async def get_by_strava_id(self, activity_id: int) -> CompletedWorkout | None:
        result = await self._session.execute(
            select(CompletedWorkout).where(CompletedWorkout.strava_activity_id == activity_id)
        )
        return result.scalars().first()

    async def get_week(self, week_start: date, week_end: date) -> list[CompletedWorkout]:
        result = await self._session.execute(
            select(CompletedWorkout)
            .where(
                CompletedWorkout.workout_date >= week_start,
                CompletedWorkout.workout_date <= week_end,
            )
            .order_by(CompletedWorkout.started_at)
        )
        return list(result.scalars().all())

    async def upsert_from_strava(self, payload: dict[str, Any]) -> CompletedWorkout:
        """Upsert по strava_activity_id. payload — сырой ответ Strava API."""
        activity_id = int(payload["id"])
        started_at = datetime.fromisoformat(payload["start_date_local"].replace("Z", "+00:00")).replace(tzinfo=None)
        distance_km = round(float(payload.get("distance", 0) or 0) / 1000.0, 3)
        duration_minutes = int(round(float(payload.get("moving_time", 0) or 0) / 60.0))
        activity_type = str(payload.get("type", ""))
        now = datetime.utcnow()

        values = {
            "strava_activity_id": activity_id,
            "workout_date": started_at.date(),
            "activity_type": activity_type,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "started_at": started_at,
            "raw_json": payload,
            "fetched_at": now,
        }
        stmt = (
            insert(CompletedWorkout)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["strava_activity_id"],
                set_={
                    "workout_date": values["workout_date"],
                    "activity_type": values["activity_type"],
                    "distance_km": values["distance_km"],
                    "duration_minutes": values["duration_minutes"],
                    "started_at": values["started_at"],
                    "raw_json": values["raw_json"],
                    "fetched_at": values["fetched_at"],
                },
            )
            .returning(CompletedWorkout)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def delete_by_strava_id(self, activity_id: int) -> bool:
        result = await self._session.execute(
            delete(CompletedWorkout).where(CompletedWorkout.strava_activity_id == activity_id)
        )
        await self._session.flush()
        return result.rowcount > 0

    async def update_distance_override(
        self, record_id: int, distance_km: float | None
    ) -> CompletedWorkout | None:
        return await self.update(record_id, distance_km_override=distance_km)
