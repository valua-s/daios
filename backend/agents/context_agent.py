from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.agents.base import BaseAgent
from backend.core.config import settings
from backend.integrations.bus_schedule import BusArrival, BusScheduleParser
from backend.integrations.weather import WeatherClient, WeatherData

logger = logging.getLogger(__name__)
START_WEEKEND_DAY = 5


def _is_weekend(target_date: date) -> bool:
    return target_date.weekday() >= START_WEEKEND_DAY


class ContextAgent(BaseAgent):
    """Собирает внешний контекст дня: погоду и расписание автобусов.

    Логика:
    - Будни: погода + автобусы
    - Выходные: только погода (автобусы не нужны)
    """

    def __init__(
        self,
        weather_client: WeatherClient,
        bus_parser: BusScheduleParser,
    ) -> None:
        self._weather = weather_client
        self._bus = bus_parser

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        today = datetime.now(ZoneInfo(settings.app_timezone)).date()
        is_weekend = _is_weekend(today)

        weather: WeatherData | None = None
        bus_schedule: list[BusArrival] = []

        try:
            weather = await self._weather.get_current_weather()
        except Exception:
            logger.exception("Failed to fetch weather")

        if not is_weekend:
            try:
                bus_schedule = await self._bus.get_next_departures(
                    url=settings.bus_schedule_url,
                )
            except Exception:
                logger.exception("Failed to fetch bus schedule")

        return {
            **state,
            "weather": weather,
            "bus_schedule": bus_schedule,
            "is_weekend": is_weekend,
        }
