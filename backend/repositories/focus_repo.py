from __future__ import annotations

from sqlalchemy import select

from backend.models.focus import Focus, FocusPeriod
from backend.repositories.base import BaseRepository


class FocusRepository(BaseRepository[Focus]):
    model = Focus

    async def get_active(self, period: FocusPeriod) -> Focus | None:
        result = await self._session.execute(
            select(Focus).where(
                Focus.period == period,
                Focus.is_active.is_(True),
            ).order_by(Focus.created_at.desc())
        )
        return result.scalars().first()

    async def deactivate_period(self, period: FocusPeriod) -> None:
        """Деактивировать все записи периода перед установкой нового фокуса."""
        all_active = await self._session.execute(
            select(Focus).where(
                Focus.period == period,
                Focus.is_active.is_(True),
            )
        )
        for focus in all_active.scalars().all():
            focus.is_active = False
        await self._session.flush()
