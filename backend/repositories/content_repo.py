from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update

from backend.models.content import ContentItem, ContentStatus
from backend.repositories.base import BaseRepository


class ContentRepository(BaseRepository[ContentItem]):
    model = ContentItem

    async def get_by_url(self, url: str) -> ContentItem | None:
        result = await self._session.execute(
            select(ContentItem).where(ContentItem.url == url)
        )
        return result.scalar_one_or_none()

    async def get_new_by_topic(self, topic: str, limit: int = 10) -> list[ContentItem]:
        result = await self._session.execute(
            select(ContentItem)
            .where(ContentItem.topic == topic, ContentItem.status == ContentStatus.new)
            .order_by(ContentItem.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_queued(self) -> list[ContentItem]:
        result = await self._session.execute(
            select(ContentItem).where(ContentItem.status == ContentStatus.queued)
        )
        return list(result.scalars().all())

    async def mark_shown(self, item_id: int) -> None:
        await self._session.execute(
            update(ContentItem)
            .where(ContentItem.id == item_id)
            .values(status=ContentStatus.shown, shown_at=datetime.now(tz=timezone.utc))
        )
