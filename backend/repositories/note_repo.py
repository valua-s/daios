from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.models.note import Note, NoteItem
from backend.repositories.base import BaseRepository


class NoteRepository(BaseRepository[Note]):
    model = Note

    async def get_all_ordered(self) -> list[Note]:
        result = await self._session.execute(
            select(Note)
            .options(selectinload(Note.items))
            .order_by(Note.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_with_items(self, note_id: int) -> Note | None:
        result = await self._session.execute(
            select(Note).options(selectinload(Note.items)).where(Note.id == note_id)
        )
        return result.scalar_one_or_none()


class NoteItemRepository(BaseRepository[NoteItem]):
    model = NoteItem

    async def get_max_sort_order(self, note_id: int) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(NoteItem.sort_order), -1)).where(
                NoteItem.note_id == note_id
            )
        )
        return int(result.scalar_one())
