from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.agents.base import BaseAgent
from backend.core.config import settings
from backend.integrations.weather import WeatherClient, WeatherData

if TYPE_CHECKING:
    from datetime import date
    from typing import Any

logger = logging.getLogger(__name__)
START_WEEKEND_DAY = 5


def _is_weekend(target_date: date) -> bool:
    return target_date.weekday() >= START_WEEKEND_DAY


class ContextAgent(BaseAgent):
    """Собирает внешний контекст дня: погоду."""

    def __init__(self, weather_client: WeatherClient) -> None:
        self._weather = weather_client

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()

        weather: WeatherData | None = None
        try:
            weather = await self._weather.get_current_weather()
        except Exception:
            logger.exception("Failed to fetch weather")

        return {
            **state,
            "weather": weather,
            "is_weekend": _is_weekend(today),
        }
