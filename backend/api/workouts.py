from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get, patch
from litestar.exceptions import HTTPException

from backend.core.config import settings
from backend.repositories.completed_workout_repo import CompletedWorkoutRepository
from backend.services.strava_service import StravaService
from backend.services.workout_service import WorkoutService

DAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]


@dataclass
class WorkoutDTO:
    day: str
    date: str
    type: str
    description: str
    duration_minutes: int
    is_today: bool
    is_completed: bool = False
    actual_distance_km: float | None = None
    actual_duration_minutes: int | None = None
    completed_workout_id: int | None = None
    details: dict = field(default_factory=dict)


@dataclass
class WeekSummaryDTO:
    planned_km: float
    actual_km: float
    percent: int


@dataclass
class UpdateDistanceRequest:
    distance_km: float | None


class WorkoutController(Controller):
    path = "/api/workouts"

    @get("/week")
    async def get_week(
        self,
        workout_service: FromDishka[WorkoutService],
        completed_repo: FromDishka[CompletedWorkoutRepository],
    ) -> list[WorkoutDTO]:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        completed_records = await completed_repo.get_week(monday, sunday)
        completed_by_date = {r.workout_date: r for r in completed_records}

        result = []
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            completed = completed_by_date.get(d)
            result.append(WorkoutDTO(
                day=DAYS_RU[i],
                date=d.isoformat(),
                type=plan.type if plan else "rest",
                description=plan.description if plan else "—",
                duration_minutes=plan.duration_minutes if plan else 0,
                is_today=d == today,
                is_completed=completed is not None,
                actual_distance_km=completed.effective_distance_km if completed else None,
                actual_duration_minutes=completed.duration_minutes if completed else None,
                completed_workout_id=completed.id if completed else None,
                details=plan.details if plan else {},
            ))
        return result

    @get("/week/summary")
    async def get_week_summary(
        self,
        workout_service: FromDishka[WorkoutService],
        strava_service: FromDishka[StravaService],
    ) -> WeekSummaryDTO:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        planned_km = 0.0
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            if plan and plan.type in {"running", "combined"}:
                planned_km += float(plan.details.get("total_km", 0) or 0)

        summary = await strava_service.weekly_running_summary(monday, sunday, planned_km)
        return WeekSummaryDTO(
            planned_km=summary.planned_km,
            actual_km=summary.actual_km,
            percent=summary.percent,
        )

    @patch("/completed/{completed_id:int}")
    async def update_completed_distance(
        self,
        completed_id: int,
        data: UpdateDistanceRequest,
        strava_service: FromDishka[StravaService],
    ) -> dict[str, str]:
        ok = await strava_service.set_distance_override(completed_id, data.distance_km)
        if not ok:
            raise HTTPException(status_code=404, detail="Completed workout not found")
        return {"status": "ok"}
