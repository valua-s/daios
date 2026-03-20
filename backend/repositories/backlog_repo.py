from __future__ import annotations

from sqlalchemy import select

from backend.models.backlog import BacklogItem
from backend.repositories.base import BaseRepository


class BacklogRepository(BaseRepository[BacklogItem]):
    model = BacklogItem

    async def get_all_ordered(self) -> list[BacklogItem]:
        result = await self._session.execute(
            select(BacklogItem).order_by(BacklogItem.created_at.desc())
        )
        return list(result.scalars().all())
