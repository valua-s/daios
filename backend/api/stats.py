from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get
from litestar.params import Parameter

from backend.services.stats_service import DayStats, StatsService


@dataclass
class WorkoutTypeStatsDTO:
    type: str
    count: int
    distance_km: float
    duration_minutes: int


@dataclass
class DayStatsDTO:
    date: str
    tasks_total: int
    tasks_done: int
    tasks_pending: int
    tasks_cancelled: int
    tasks_percent: int
    workouts_count: int
    workouts_distance_km: float
    workouts_duration_minutes: int
    workouts_by_type: list[WorkoutTypeStatsDTO] = field(default_factory=list)


def _to_dto(stats: DayStats) -> DayStatsDTO:
    return DayStatsDTO(
        date=stats.date.isoformat(),
        tasks_total=stats.tasks_total,
        tasks_done=stats.tasks_done,
        tasks_pending=stats.tasks_pending,
        tasks_cancelled=stats.tasks_cancelled,
        tasks_percent=stats.tasks_percent,
        workouts_count=stats.workouts_count,
        workouts_distance_km=stats.workouts_distance_km,
        workouts_duration_minutes=stats.workouts_duration_minutes,
        workouts_by_type=[
            WorkoutTypeStatsDTO(
                type=w.type,
                count=w.count,
                distance_km=w.distance_km,
                duration_minutes=w.duration_minutes,
            )
            for w in stats.workouts_by_type
        ],
    )


class StatsController(Controller):
    path = "/api/stats"

    @get("/today")
    async def get_today(self, stats_service: FromDishka[StatsService]) -> DayStatsDTO:  # noqa: PLR6301
        return _to_dto(await stats_service.get_day_stats())

    @get("/day")
    async def get_day(  # noqa: PLR6301
        self,
        stats_service: FromDishka[StatsService],
        target_date: date = Parameter(query="date"),  # noqa: B008
    ) -> DayStatsDTO:
        return _to_dto(await stats_service.get_day_stats(target_date))
