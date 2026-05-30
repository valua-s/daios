from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from backend.models.completed_workout import CompletedWorkout
from backend.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import date


class CompletedWorkoutRepository(BaseRepository[CompletedWorkout]):
    model = CompletedWorkout

    async def get_by_date(self, workout_date: date) -> CompletedWorkout | None:
        result = await self._session.execute(
            select(CompletedWorkout).where(CompletedWorkout.workout_date == workout_date)
        )
        return result.scalars().first()

    async def get_week(self, week_start: date, week_end: date) -> list[CompletedWorkout]:
        result = await self._session.execute(
            select(CompletedWorkout)
            .where(
                CompletedWorkout.workout_date >= week_start,
                CompletedWorkout.workout_date <= week_end,
            )
            .order_by(CompletedWorkout.workout_date)
        )
        return list(result.scalars().all())

    async def upsert(
        self,
        workout_date: date,
        activity_type: str,
        distance_km: float,
        duration_minutes: int,
        note: str | None = None,
    ) -> CompletedWorkout:
        values = {
            "workout_date": workout_date,
            "activity_type": activity_type,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "note": note,
        }
        stmt = (
            insert(CompletedWorkout)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["workout_date"],
                set_={k: v for k, v in values.items() if k != "workout_date"},
            )
            .returning(CompletedWorkout)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()
