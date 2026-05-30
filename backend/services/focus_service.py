from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.focus import Focus, FocusPeriod
from backend.repositories.focus_repo import FocusRepository

if TYPE_CHECKING:
    from datetime import date


def _today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _week_key(d: date) -> str:
    return f"{d.year}-W{d.isocalendar().week:02d}"


def _month_key(d: date) -> str:
    return f"{d.year}-{d.month:02d}"


class FocusService:
    """Бизнес-логика фокуса недели и месяца."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = FocusRepository(session)
        self._session = session

    async def get_current_week_focus(self) -> Focus | None:
        return await self._repo.get_active(FocusPeriod.week)

    async def get_current_month_focus(self) -> Focus | None:
        return await self._repo.get_active(FocusPeriod.month)

    async def set_week_focus(self, description: str) -> Focus:
        await self._repo.deactivate_period(FocusPeriod.week)
        return await self._repo.create(
            period=FocusPeriod.week,
            period_key=_week_key(_today()),
            description=description,
            is_active=True,
        )

    async def set_month_focus(self, description: str) -> Focus:
        await self._repo.deactivate_period(FocusPeriod.month)
        return await self._repo.create(
            period=FocusPeriod.month,
            period_key=_month_key(_today()),
            description=description,
            is_active=True,
        )
