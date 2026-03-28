from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings

_tz = ZoneInfo(settings.app_timezone)


def _today() -> date:
    return datetime.now(_tz).date()


from backend.integrations.google_sheets import (
    GoogleSheetsClient,
    parse_workout_text,
)
from backend.models.workout_cache import WorkoutCache
from backend.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


@dataclass
class WorkoutPlan:
    type: str            # "running" | "strength" | "combined" | "rest"
    description: str
    duration_minutes: int
    details: dict


class WorkoutCacheRepository(BaseRepository[WorkoutCache]):
    model = WorkoutCache


class WorkoutService:
    """Тренировки.

    - get_workout_for_date  — только из DB, без обращения к Sheets
    - sync_week             — синхронизирует неделю из Sheets → DB
    """

    def __init__(self, session: AsyncSession, sheets_client: GoogleSheetsClient) -> None:
        self._session = session
        self._sheets = sheets_client
        self._cache_repo = WorkoutCacheRepository(session)

    # ── Чтение из DB ──────────────────────────────────────────────────────

    async def get_workout_for_date(self, target_date: date) -> WorkoutPlan | None:
        result = await self._session.execute(
            select(WorkoutCache).where(WorkoutCache.date == target_date)
        )
        cached = result.scalars().first()
        return self._deserialize(cached.data_json) if cached else None

    # ── Синхронизация из Google Sheets → DB ───────────────────────────────

    async def sync_week(self, week_start: date | None = None) -> int:
        """Загружает все 7 дней недели из Sheets в DB. Возвращает кол-во записей."""
        if week_start is None:
            today = _today()
            week_start = today - timedelta(days=today.weekday())

        synced = 0
        for i in range(7):
            d = week_start + timedelta(days=i)
            try:
                raw = await self._sheets.get_workout_for_date(d)
                plan = WorkoutPlan(**parse_workout_text(raw["raw"] if raw else ""))
                await self._upsert_cache(d, plan)
                synced += 1
            except Exception:
                logger.exception("Failed to sync workout for %s", d)

        logger.info("Synced %d workout days starting %s", synced, week_start)
        return synced

    # ── Внутренние методы ─────────────────────────────────────────────────

    async def _upsert_cache(self, target_date: date, plan: WorkoutPlan) -> None:
        await self._session.execute(
            delete(WorkoutCache).where(WorkoutCache.date == target_date)
        )
        await self._cache_repo.create(
            date=target_date,
            data_json=json.dumps(
                {
                    "type": plan.type,
                    "description": plan.description,
                    "duration_minutes": plan.duration_minutes,
                    "details": plan.details,
                },
                ensure_ascii=False,
            ),
            fetched_at=datetime.now(tz=_tz),
        )

    @staticmethod
    def _deserialize(data_json: str) -> WorkoutPlan:
        return WorkoutPlan(**json.loads(data_json))
