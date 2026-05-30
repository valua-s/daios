from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.agents.base import BaseAgent
from backend.core.config import settings
from backend.services.workout_service import WorkoutService

if TYPE_CHECKING:
    from datetime import date
    from typing import Any

logger = logging.getLogger(__name__)


class WorkoutAgent(BaseAgent):
    """Получает план тренировки на день и рассчитывает время.

    Встраивает результат в state для Orchestrator.
    """

    def __init__(self, workout_service: WorkoutService) -> None:
        self._service = workout_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        target_date: date = state.get("date", datetime.now(ZoneInfo(settings.app_timezone)).date())

        try:
            workout = await self._service.get_workout_for_date(target_date)
        except Exception:
            logger.exception("Failed to fetch workout for %s", target_date)
            workout = None

        return {
            **state,
            "workout": workout,
        }
