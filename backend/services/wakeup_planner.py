from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from backend.core.config import settings
from backend.integrations.weather import WeatherClient
from backend.services.settings_service import SettingsService
from backend.services.workout_service import WorkoutPlan, WorkoutService

if TYPE_CHECKING:
    from typing import Literal

logger = logging.getLogger(__name__)

PREP_MINUTES = 15
MORNING_MAX_DURATION = 60
WEEKEND_START_DAY = 5


@dataclass
class WakeupPlan:
    workout: WorkoutPlan
    when: Literal["morning", "evening"]
    alarm_time: time
    rain_expected: bool | None  # None — прогноз не запрашивался / упал


def _shift(base: time, minus_minutes: int, on_date: date) -> time:
    """Сдвигает time на N минут назад в рамках того же дня (без перехода через сутки)."""
    base_dt = datetime.combine(on_date, base)
    shifted = base_dt - timedelta(minutes=minus_minutes)
    return shifted.time()


class WakeupPlanner:
    """Решает, ставить ли завтрашнюю тренировку на утро или на вечер,

    и считает время будильника.
    """

    def __init__(
        self,
        workout_service: WorkoutService,
        weather_client: WeatherClient,
        settings_service: SettingsService,
    ) -> None:
        self._workouts = workout_service
        self._weather = weather_client
        self._settings = settings_service

    async def plan_for_tomorrow(self, today: date) -> WakeupPlan | None:
        tomorrow = today + timedelta(days=1)
        if tomorrow.weekday() >= WEEKEND_START_DAY:
            return None

        workout = await self._workouts.get_workout_for_date(tomorrow)
        if workout is None or workout.type == "rest":
            return None

        base = await self._settings.get_wakeup_base_time()
        duration = workout.duration_minutes
        morning_alarm = _shift(base, PREP_MINUTES + duration, tomorrow)

        when: Literal["morning", "evening"]
        rain: bool | None
        if duration <= MORNING_MAX_DURATION:
            tz = ZoneInfo(settings.app_timezone)
            window_start = datetime.combine(
                tomorrow, _shift(base, duration, tomorrow), tzinfo=tz,
            )
            window_end = datetime.combine(tomorrow, base, tzinfo=tz)
            try:
                rain = await self._weather.get_forecast_rain(window_start, window_end)
            except Exception:
                logger.exception("Forecast failed; defaulting tomorrow workout to evening")
                rain = None
                when = "evening"
            else:
                when = "evening" if rain else "morning"
        else:
            when = "evening"
            rain = None

        alarm = morning_alarm if when == "morning" else base
        return WakeupPlan(workout=workout, when=when, alarm_time=alarm, rain_expected=rain)
