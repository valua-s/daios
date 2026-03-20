from __future__ import annotations

from datetime import date
from typing import Any

from backend.agents.base import BaseAgent
from backend.services.workout_service import WorkoutService


class WorkoutAgent(BaseAgent):
    """Получает план тренировки на день и рассчитывает время.
    Встраивает результат в state для Orchestrator.
    """

    def __init__(self, workout_service: WorkoutService) -> None:
        self._service = workout_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        target_date: date = state.get("date", date.today())

        workout = await self._service.get_workout_for_date(target_date)

        return {
            **state,
            "workout": workout,  # None если тренировки нет
        }
