from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, post
from litestar.exceptions import HTTPException

from backend.core.config import settings
from backend.repositories.completed_workout_repo import (
    CompletedWorkoutRepository,
)
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
class CompleteWorkoutRequest:
    workout_date: str
    distance_km: float = 0.0
    duration_minutes: int = 0
    activity_type: str = "running"
    note: str | None = None


class WorkoutController(Controller):
    path = "/api/workouts"

    @get("/week")
    async def get_week(  # noqa: PLR6301
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
                actual_distance_km=completed.distance_km if completed else None,
                actual_duration_minutes=completed.duration_minutes if completed else None,
                completed_workout_id=completed.id if completed else None,
                details=plan.details if plan else {},
            ))
        return result

    @get("/week/summary")
    async def get_week_summary(  # noqa: PLR6301
        self,
        workout_service: FromDishka[WorkoutService],
        completed_repo: FromDishka[CompletedWorkoutRepository],
    ) -> WeekSummaryDTO:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)

        planned_km = 0.0
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            if plan:
                planned_km += float(plan.details.get("run_km", plan.details.get("total_km", 0)) or 0)

        records = await completed_repo.get_week(monday, sunday)
        actual = round(sum(r.distance_km for r in records if r.activity_type in {"running", "combined"}), 2)
        percent = round(actual / planned_km * 100) if planned_km > 0 else 0
        return WeekSummaryDTO(
            planned_km=round(planned_km, 2),
            actual_km=actual,
            percent=percent,
        )

    @post("/completed")
    async def upsert_completed(  # noqa: PLR6301
        self,
        data: CompleteWorkoutRequest,
        completed_repo: FromDishka[CompletedWorkoutRepository],
    ) -> dict[str, int]:
        try:
            wdate = date.fromisoformat(data.workout_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Bad workout_date") from exc
        record = await completed_repo.upsert(
            workout_date=wdate,
            activity_type=data.activity_type or "running",
            distance_km=max(0.0, float(data.distance_km or 0)),
            duration_minutes=max(0, int(data.duration_minutes or 0)),
            note=data.note,
        )
        return {"id": record.id}

    @delete("/completed/{completed_id:int}")
    async def delete_completed(  # noqa: PLR6301
        self,
        completed_id: int,
        completed_repo: FromDishka[CompletedWorkoutRepository],
    ) -> None:
        ok = await completed_repo.delete(completed_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Completed workout not found")
