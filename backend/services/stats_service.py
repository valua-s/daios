from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.task import TaskStatus
from backend.repositories.completed_workout_repo import (
    CompletedWorkoutRepository,
)
from backend.repositories.task_repo import TaskRepository

if TYPE_CHECKING:
    from datetime import date


def _today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


@dataclass
class WorkoutTypeStats:
    """Факт по одной дисциплине за день."""

    type: str
    count: int
    distance_km: float
    duration_minutes: int


@dataclass
class DayStats:
    """Итоги дня: задачи и проведённые тренировки."""

    date: date
    tasks_total: int
    tasks_done: int
    tasks_pending: int
    tasks_cancelled: int
    tasks_percent: int
    workouts_count: int
    workouts_distance_km: float
    workouts_duration_minutes: int
    workouts_by_type: list[WorkoutTypeStats] = field(default_factory=list)


class StatsService:
    """Сводная статистика за день — задачи + фактические тренировки."""

    def __init__(self, session: AsyncSession) -> None:
        self._tasks = TaskRepository(session)
        self._workouts = CompletedWorkoutRepository(session)

    async def get_day_stats(self, target_date: date | None = None) -> DayStats:
        day = target_date or _today()

        tasks = await self._tasks.get_by_date(day)
        done = sum(1 for t in tasks if t.status == TaskStatus.done)
        pending = sum(1 for t in tasks if t.status == TaskStatus.pending)
        cancelled = sum(1 for t in tasks if t.status == TaskStatus.cancelled)
        # Отменённые не считаем — они не влияют на прогресс дня.
        countable = done + pending

        records = await self._workouts.get_by_date(day)
        by_type: dict[str, WorkoutTypeStats] = {}
        for r in records:
            stats = by_type.get(r.activity_type)
            if stats is None:
                stats = WorkoutTypeStats(
                    type=r.activity_type,
                    count=0,
                    distance_km=0.0,
                    duration_minutes=0,
                )
                by_type[r.activity_type] = stats
            stats.count += 1
            stats.distance_km += r.distance_km
            stats.duration_minutes += r.duration_minutes

        for stats in by_type.values():
            stats.distance_km = round(stats.distance_km, 2)

        return DayStats(
            date=day,
            tasks_total=len(tasks),
            tasks_done=done,
            tasks_pending=pending,
            tasks_cancelled=cancelled,
            tasks_percent=round(done / countable * 100) if countable else 0,
            workouts_count=len(records),
            workouts_distance_km=round(sum(r.distance_km for r in records), 2),
            workouts_duration_minutes=sum(r.duration_minutes for r in records),
            workouts_by_type=sorted(by_type.values(), key=lambda s: s.type),
        )
