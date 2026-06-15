from __future__ import annotations

from sqlalchemy import select

from backend.models.diary import DiaryEntry
from backend.repositories.base import BaseRepository


class DiaryRepository(BaseRepository[DiaryEntry]):
    model = DiaryEntry

    async def get_all_ordered(self) -> list[DiaryEntry]:
        result = await self._session.execute(
            select(DiaryEntry).order_by(DiaryEntry.created_at.desc())
        )
        return list(result.scalars().all())
