from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, post
from litestar.exceptions import HTTPException

from backend.core.config import settings
from backend.repositories.completed_workout_repo import (
    CompletedWorkoutRepository,
)
from backend.services.workout_service import WorkoutService

if TYPE_CHECKING:
    from collections.abc import Sequence

    from backend.models.completed_workout import CompletedWorkout

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

DISCIPLINE_UNITS = {
    "running": "km",
    "cycling": "km",
    "swimming": "m",
    "strength": "min",
}


@dataclass
class ActualWorkoutDTO:
    id: int
    type: str
    distance_km: float
    duration_minutes: int
    source: str
    note: str | None = None


@dataclass
class WorkoutDTO:
    day: str
    date: str
    type: str
    description: str
    duration_minutes: int
    is_today: bool
    is_completed: bool = False
    actuals: list[ActualWorkoutDTO] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class DisciplineSummaryDTO:
    type: str
    unit: str          # "km" | "m" | "min"
    planned: float
    actual: float
    percent: int


@dataclass
class WeekSummaryDTO:
    planned_km: float
    actual_km: float
    percent: int
    disciplines: list[DisciplineSummaryDTO] = field(default_factory=list)


@dataclass
class CompleteWorkoutRequest:
    workout_date: str
    distance_km: float = 0.0
    duration_minutes: int = 0
    activity_type: str = "running"
    note: str | None = None


def _empty_totals() -> dict[str, float]:
    return {"km": 0.0, "m": 0.0, "min": 0.0}


def _add_plan_segments(planned: dict[str, dict[str, float]], details: dict) -> None:
    for seg in details.get("segments", []):
        discipline = seg.get("discipline")
        if discipline not in DISCIPLINE_UNITS:
            continue
        totals = planned[discipline]
        totals["km"] += float(seg.get("distance_km") or 0)
        totals["m"] += float(seg.get("distance_m") or 0)
        totals["min"] += float(seg.get("minutes") or 0)


def _rounded(value: float, unit: str) -> float:
    return round(value, 2) if unit == "km" else round(value)


def _actual_totals(records: Sequence[CompletedWorkout]) -> dict[str, dict[str, float]]:
    actual: dict[str, dict[str, float]] = defaultdict(_empty_totals)
    for r in records:
        # "combined" остался в старых записях — засчитываем его как бег.
        discipline = "running" if r.activity_type == "combined" else r.activity_type
        if discipline not in DISCIPLINE_UNITS:
            continue
        totals = actual[discipline]
        totals["km"] += r.distance_km
        totals["m"] += r.distance_km * 1000
        totals["min"] += r.duration_minutes
    return actual


def _discipline_summaries(
    planned: dict[str, dict[str, float]],
    records: Sequence[CompletedWorkout],
) -> list[DisciplineSummaryDTO]:
    actual = _actual_totals(records)
    summaries = []
    for discipline, unit in DISCIPLINE_UNITS.items():
        plan_totals = planned.get(discipline, _empty_totals())
        fact_totals = actual.get(discipline, _empty_totals())
        # План без дистанции задан временем — сравниваем минуты.
        effective = "min" if unit != "min" and plan_totals[unit] == 0 else unit
        plan_value = _rounded(plan_totals[effective], effective)
        fact_value = _rounded(fact_totals[effective], effective)
        if plan_value == 0 and fact_value == 0:
            continue
        summaries.append(DisciplineSummaryDTO(
            type=discipline,
            unit=effective,
            planned=plan_value,
            actual=fact_value,
            percent=round(fact_value / plan_value * 100) if plan_value > 0 else 0,
        ))
    return summaries


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
        completed_by_date: dict[date, list[ActualWorkoutDTO]] = defaultdict(list)
        for r in completed_records:
            completed_by_date[r.workout_date].append(ActualWorkoutDTO(
                id=r.id,
                type=r.activity_type,
                distance_km=r.distance_km,
                duration_minutes=r.duration_minutes,
                source=r.source,
                note=r.note,
            ))

        result = []
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            actuals = completed_by_date.get(d, [])
            result.append(WorkoutDTO(
                day=DAYS[i],
                date=d.isoformat(),
                type=plan.type if plan else "rest",
                description=plan.description if plan else "—",
                duration_minutes=plan.duration_minutes if plan else 0,
                is_today=d == today,
                is_completed=bool(actuals),
                actuals=actuals,
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
        planned: dict[str, dict[str, float]] = defaultdict(_empty_totals)
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            if not plan:
                continue
            planned_km += float(plan.details.get("run_km", plan.details.get("total_km", 0)) or 0)
            _add_plan_segments(planned, plan.details)

        records = await completed_repo.get_week(monday, sunday)
        actual = round(sum(r.distance_km for r in records if r.activity_type in {"running", "combined"}), 2)
        percent = round(actual / planned_km * 100) if planned_km > 0 else 0
        return WeekSummaryDTO(
            planned_km=round(planned_km, 2),
            actual_km=actual,
            percent=percent,
            disciplines=_discipline_summaries(planned, records),
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
