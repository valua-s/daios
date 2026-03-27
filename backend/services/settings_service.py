from __future__ import annotations

import logging
from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.settings_repo import (
    ScheduleRepository,
    UserSettingRepository,
)

logger = logging.getLogger(__name__)

_DELETED = "__deleted__"

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
    {"event_name": "evening_икшуа", "cron_expr": "30 16 * * *", "enabled": True, "description": "Вечерняя сводка"},
]


@dataclass
class ScheduleDTO:
    event_name: str
    cron_expr: str
    enabled: bool
    description: str
    time: str  # HH:MM, только для простых ежедневных cron (одно время)


SCHEDULE_RELOAD_CHANNEL = "schedule:reload"


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
        await self._session.commit()

    async def add_interest(self, key: str) -> None:
        await self._settings.upsert(f"interests.{key}", "true")
        await self._session.commit()

    async def delete_interest(self, key: str) -> None:
        if key in DEFAULT_INTERESTS:
            # Дефолтные помечаем как удалённые, чтобы не всплывали снова
            await self._settings.upsert(f"interests.{key}", _DELETED)
        else:
            await self._settings.delete(f"interests.{key}")
        await self._session.commit()

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
        await self._session.commit()

    async def get_schedules(self) -> list[ScheduleDTO]:
        db_schedules = {s.event_name: s for s in await self._schedules.get_all()}
        result = []
        for default in DEFAULT_SCHEDULES:
            s = db_schedules.get(default["event_name"])
            cron = s.cron_expr if s else default["cron_expr"]
            enabled = s.enabled if s else default["enabled"]
            result.append(ScheduleDTO(
                event_name=default["event_name"],
                cron_expr=cron,
                enabled=enabled,
                description=default["description"],
                time=_cron_to_time(cron),
            ))
        return result

    async def update_schedule(self, event_name: str, time: str, enabled: bool) -> ScheduleDTO | None:
        default = next((d for d in DEFAULT_SCHEDULES if d["event_name"] == event_name), None)
        if default is None:
            return None
        cron = _time_to_cron(time)
        schedule = await self._schedules.upsert(
            event_name=event_name,
            cron_expr=cron,
            enabled=enabled,
            description=default["description"],
        )
        await self._session.commit()

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
        )


def _cron_to_time(cron: str) -> str:
    """'30 6 * * *' → '06:30'. Для мульти-значений ('0 6,17 * * *') берём первое."""
    parts = cron.split()
    minute, hour = parts[0], parts[1].split(",")[0]
    return f"{int(hour):02d}:{int(minute):02d}"


def _time_to_cron(time: str) -> str:
    """'06:30' → '30 6 * * *'."""
    h, m = time.split(":")
    return f"{int(m)} {int(h)} * * *"
