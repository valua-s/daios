from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.agents.base import BaseAgent
from backend.core.config import settings
from backend.services.workout_service import WorkoutService


class WorkoutAgent(BaseAgent):
    """Получает план тренировки на день и рассчитывает время.
    Встраивает результат в state для Orchestrator.
    """

    def __init__(self, workout_service: WorkoutService) -> None:
        self._service = workout_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        target_date: date = state.get("date", datetime.now(ZoneInfo(settings.app_timezone)).date())

        workout = await self._service.get_workout_for_date(target_date)

        return {
            **state,
            "workout": workout,  # None если тренировки нет
        }
