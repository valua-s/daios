from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get

from backend.core.config import settings
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
    details: dict = field(default_factory=dict)


class WorkoutController(Controller):
    path = "/api/workouts"

    @get("/week")
    async def get_week(
        self,
        workout_service: FromDishka[WorkoutService],
    ) -> list[WorkoutDTO]:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
        monday = today - timedelta(days=today.weekday())

        result = []
        for i in range(7):
            d = monday + timedelta(days=i)
            plan = await workout_service.get_workout_for_date(d)
            result.append(WorkoutDTO(
                day=DAYS_RU[i],
                date=d.isoformat(),
                type=plan.type if plan else "rest",
                description=plan.description if plan else "—",
                duration_minutes=plan.duration_minutes if plan else 0,
                is_today=d == today,
                details=plan.details if plan else {},
            ))
        return result
