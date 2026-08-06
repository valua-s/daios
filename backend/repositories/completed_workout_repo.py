from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from backend.models.completed_workout import (
    SOURCE_MANUAL,
    SOURCE_STRAVA,
    CompletedWorkout,
)
from backend.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import date, datetime

_MANUAL_ONLY = sa.text(f"source = '{SOURCE_MANUAL}'")


class CompletedWorkoutRepository(BaseRepository[CompletedWorkout]):
    model = CompletedWorkout

    async def get_by_date(self, workout_date: date) -> list[CompletedWorkout]:
        result = await self._session.execute(
            select(CompletedWorkout)
            .where(CompletedWorkout.workout_date == workout_date)
            .order_by(CompletedWorkout.started_at, CompletedWorkout.id)
        )
        return list(result.scalars().all())

    async def get_week(self, week_start: date, week_end: date) -> list[CompletedWorkout]:
        result = await self._session.execute(
            select(CompletedWorkout)
            .where(
                CompletedWorkout.workout_date >= week_start,
                CompletedWorkout.workout_date <= week_end,
            )
            .order_by(
                CompletedWorkout.workout_date,
                CompletedWorkout.started_at,
                CompletedWorkout.id,
            )
        )
        return list(result.scalars().all())

    async def get_manual_keys(
        self, week_start: date, week_end: date,
    ) -> set[tuple[date, str]]:
        """Пары (дата, тип) с ручной отметкой — синхронизация их не перезаписывает."""
        result = await self._session.execute(
            select(CompletedWorkout.workout_date, CompletedWorkout.activity_type).where(
                CompletedWorkout.source == SOURCE_MANUAL,
                CompletedWorkout.workout_date >= week_start,
                CompletedWorkout.workout_date <= week_end,
            )
        )
        return {(row.workout_date, row.activity_type) for row in result}

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
            "source": SOURCE_MANUAL,
        }
        stmt = (
            insert(CompletedWorkout)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["workout_date", "activity_type"],
                index_where=_MANUAL_ONLY,
                set_={
                    k: v
                    for k, v in values.items()
                    if k not in {"workout_date", "activity_type"}
                },
            )
            .returning(CompletedWorkout)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.scalar_one()

    async def upsert_from_strava(
        self,
        strava_activity_id: int,
        workout_date: date,
        activity_type: str,
        distance_km: float,
        duration_minutes: int,
        started_at: datetime,
        note: str | None = None,
    ) -> None:
        values = {
            "workout_date": workout_date,
            "activity_type": activity_type,
            "distance_km": distance_km,
            "duration_minutes": duration_minutes,
            "note": note,
            "source": SOURCE_STRAVA,
            "strava_activity_id": strava_activity_id,
            "started_at": started_at,
        }
        stmt = (
            insert(CompletedWorkout)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["strava_activity_id"],
                set_={k: v for k, v in values.items() if k != "strava_activity_id"},
            )
        )
        await self._session.execute(stmt)

    async def delete_strava_for_keys(self, keys: set[tuple[date, str]]) -> int:
        """Убирает записи Strava там, где та же активность отмечена вручную."""
        if not keys:
            return 0
        result = await self._session.execute(
            sa.delete(CompletedWorkout).where(
                CompletedWorkout.source == SOURCE_STRAVA,
                sa.tuple_(
                    CompletedWorkout.workout_date,
                    CompletedWorkout.activity_type,
                ).in_(keys),
            )
        )
        return result.rowcount or 0
