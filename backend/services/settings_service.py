from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import time

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.schedule import ALLOWED_EVENT_NAMES
from backend.repositories.settings_repo import (
    ScheduleRepository,
    UserSettingRepository,
)

logger = logging.getLogger(__name__)

_DELETED = "__deleted__"
_CRON_MIN_PARTS = 2
_TIME_PARTS = 2
_HOUR_MAX = 23
_MINUTE_MAX = 59

DEFAULT_INTERESTS: dict[str, bool] = {
    "python": True,
    "ai": True,
    "running": True,
    "economics": True,
    "politics": False,
}

DEFAULT_SCHEDULES: list[dict] = [
    {"event_name": "morning_brief", "cron_expr": "10 5 * * *", "enabled": True, "description": "Утренняя сводка"},
    {"event_name": "evening_summary", "cron_expr": "0 20 * * *", "enabled": True, "description": "Вечерний итог"},
    {"event_name": "collect_content", "cron_expr": "0 6 * * *", "enabled": True, "description": "Сбор контента"},
    {"event_name": "sync_workouts", "cron_expr": "0 6,17 * * *", "enabled": True, "description": "Синхронизация тренировок"},
    {"event_name": "evening_brief", "cron_expr": "30 16 * * *", "enabled": True, "description": "Вечерняя сводка"},
    {"event_name": "midnight_backlog", "cron_expr": "0 0 * * *", "enabled": True, "description": "Перенос невыполненных в бэклог"},
    {"event_name": "tasks_reminder", "cron_expr": "0 9 * * *", "enabled": True, "description": "Напоминание добавить задачи"},
]

# События, поддерживающие отдельное расписание для выходных
SPLIT_EVENTS: frozenset[str] = frozenset({"morning_brief", "evening_brief"})


@dataclass
class ScheduleDTO:
    event_name: str
    cron_expr: str
    enabled: bool
    description: str
    time: str  # HH:MM, только для простых ежедневных cron (одно время)
    cron_expr_weekend: str | None
    time_weekend: str | None
    supports_weekend: bool


SCHEDULE_RELOAD_CHANNEL = "schedule:reload"

WAKEUP_BASE_TIME_KEY = "wakeup.base_time"
WAKEUP_BASE_TIME_DEFAULT = "07:30"
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def _parse_hhmm(value: str) -> time:
    m = _TIME_RE.match(value.strip())
    if not m:
        msg = f"Invalid HH:MM time: {value!r}"
        raise ValueError(msg)
    return time(hour=int(m.group(1)), minute=int(m.group(2)))


class SettingsService:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:
        self._session = session
        self._settings = UserSettingRepository(session)
        self._schedules = ScheduleRepository(session)
        self._redis = redis

    # ── Интересы ──────────────────────────────────────────────────────────

    async def get_interests(self) -> dict[str, bool]:
        all_settings = await self._settings.get_all()
        result: dict[str, bool] = {}
        # Defaults — показываем если не удалены
        for key, default_val in DEFAULT_INTERESTS.items():
            val = all_settings.get(f"interests.{key}")
            if val is None:
                result[key] = default_val
            elif val != _DELETED:
                result[key] = val.lower() == "true"
        # Кастомные из DB
        for db_key, db_val in all_settings.items():
            if db_key.startswith("interests.") and db_val != _DELETED:
                key = db_key[len("interests."):]
                if key not in DEFAULT_INTERESTS:
                    result[key] = db_val.lower() == "true"
        return result

    async def set_interests(self, interests: dict[str, bool]) -> None:
        for key, value in interests.items():
            await self._settings.upsert(f"interests.{key}", str(value).lower())

    async def add_interest(self, key: str) -> None:
        await self._settings.upsert(f"interests.{key}", "true")

    async def delete_interest(self, key: str) -> None:
        if key in DEFAULT_INTERESTS:
            # Дефолтные помечаем как удалённые, чтобы не всплывали снова
            await self._settings.upsert(f"interests.{key}", _DELETED)
        else:
            await self._settings.delete(f"interests.{key}")

    # ── Время подъёма ─────────────────────────────────────────────────────

    async def get_wakeup_base_time(self) -> time:
        all_settings = await self._settings.get_all()
        raw = all_settings.get(WAKEUP_BASE_TIME_KEY, WAKEUP_BASE_TIME_DEFAULT)
        try:
            return _parse_hhmm(raw)
        except ValueError:
            logger.warning("Invalid wakeup.base_time in DB: %r, using default", raw)
            return _parse_hhmm(WAKEUP_BASE_TIME_DEFAULT)

    async def set_wakeup_base_time(self, value: str) -> None:
        _parse_hhmm(value)  # validate
        await self._settings.upsert(WAKEUP_BASE_TIME_KEY, value)

    # ── Расписание ────────────────────────────────────────────────────────

    async def ensure_default_schedules(self) -> None:
        """Создаёт записи расписаний в БД если их нет."""
        existing = {s.event_name for s in await self._schedules.get_all()}
        for default in DEFAULT_SCHEDULES:
            if default["event_name"] not in existing:
                await self._schedules.upsert(
                    event_name=default["event_name"],
                    cron_expr=default["cron_expr"],
                    enabled=default["enabled"],
                    description=default["description"],
                )

    async def get_schedules(self) -> list[ScheduleDTO]:
        db_schedules = {s.event_name: s for s in await self._schedules.get_all()}
        result = []
        for default in DEFAULT_SCHEDULES:
            event_name = default["event_name"]
            s = db_schedules.get(event_name)
            cron = s.cron_expr if s else default["cron_expr"]
            cron_we = s.cron_expr_weekend if s else None
            enabled = s.enabled if s else default["enabled"]
            result.append(ScheduleDTO(
                event_name=event_name,
                cron_expr=cron,
                enabled=enabled,
                description=default["description"],
                time=_cron_to_time(cron),
                cron_expr_weekend=cron_we,
                time_weekend=_cron_to_time(cron_we) if cron_we else None,
                supports_weekend=event_name in SPLIT_EVENTS,
            ))
        return result

    async def update_schedule(
        self,
        event_name: str,
        time: str,
        *,
        enabled: bool,
        time_weekend: str | None = None,
    ) -> ScheduleDTO | None:
        if event_name not in ALLOWED_EVENT_NAMES:
            msg = f"Unknown event_name: {event_name!r}"
            raise ValueError(msg)
        default = next((d for d in DEFAULT_SCHEDULES if d["event_name"] == event_name), None)
        if default is None:
            return None
        cron = _time_to_cron(time)
        cron_we: str | None = None
        if event_name in SPLIT_EVENTS and time_weekend:
            cron_we = _time_to_cron(time_weekend)
        schedule = await self._schedules.upsert(
            event_name=event_name,
            cron_expr=cron,
            enabled=enabled,
            description=default["description"],
            cron_expr_weekend=cron_we,
        )

        # Сигнал scheduler'у перечитать расписания
        try:
            await self._redis.publish(SCHEDULE_RELOAD_CHANNEL, "reload")
        except Exception:
            logger.warning("Failed to publish schedule reload signal", exc_info=True)

        return ScheduleDTO(
            event_name=schedule.event_name,
            cron_expr=schedule.cron_expr,
            enabled=schedule.enabled,
            description=schedule.description or default["description"],
            time=_cron_to_time(schedule.cron_expr),
            cron_expr_weekend=schedule.cron_expr_weekend,
            time_weekend=_cron_to_time(schedule.cron_expr_weekend) if schedule.cron_expr_weekend else None,
            supports_weekend=event_name in SPLIT_EVENTS,
        )


def _cron_to_time(cron: str) -> str:
    """'30 6 * * *' → '06:30'. Для мульти-значений ('0 6,17 * * *') берём первое."""
    parts = cron.split()
    if len(parts) < _CRON_MIN_PARTS:
        return "00:00"
    minute, hour = parts[0], parts[1].split(",")[0]
    try:
        return f"{int(hour):02d}:{int(minute):02d}"
    except ValueError:
        return "00:00"


def _time_to_cron(t: str) -> str:
    """'06:30' → '30 6 * * *'."""
    parts = t.split(":")
    if len(parts) != _TIME_PARTS:
        msg = f"Invalid time format: {t!r}, expected HH:MM"
        raise ValueError(msg)
    h, m = parts
    try:
        hour, minute = int(h), int(m)
    except ValueError as e:
        msg = f"Invalid time format: {t!r}, expected HH:MM"
        raise ValueError(msg) from e
    if not (0 <= hour <= _HOUR_MAX and 0 <= minute <= _MINUTE_MAX):
        msg = f"Time out of range: {t!r}"
        raise ValueError(msg)
    return f"{minute} {hour} * * *"
