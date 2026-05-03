from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.note import Note, NoteItem
from backend.repositories.note_repo import NoteItemRepository, NoteRepository


class NoteService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._notes = NoteRepository(session)
        self._items = NoteItemRepository(session)

    async def list_notes(self) -> list[Note]:
        return await self._notes.get_all_ordered()

    async def get_note(self, note_id: int) -> Note | None:
        return await self._notes.get_with_items(note_id)

    async def create_note(self, title: str, body: str | None = None) -> Note:
        note = await self._notes.create(title=title, body=body)
        await self._session.refresh(note, ["items"])
        return note

    async def update_note(
        self,
        note_id: int,
        title: str | None = None,
        body: str | None = None,
        *,
        clear_body: bool = False,
    ) -> Note | None:
        fields: dict[str, object] = {}
        if title is not None:
            fields["title"] = title
        if clear_body:
            fields["body"] = None
        elif body is not None:
            fields["body"] = body
        if fields:
            updated = await self._notes.update(note_id, **fields)
            if updated is None:
                return None
        return await self._notes.get_with_items(note_id)

    async def delete_note(self, note_id: int) -> bool:
        return await self._notes.delete(note_id)

    async def add_item(self, note_id: int, text: str) -> NoteItem | None:
        note = await self._notes.get(note_id)
        if note is None:
            return None
        next_order = await self._items.get_max_sort_order(note_id) + 1
        return await self._items.create(
            note_id=note_id, text=text, checked=False, sort_order=next_order
        )

    async def update_item(
        self,
        item_id: int,
        text: str | None = None,
        *,
        checked: bool | None = None,
    ) -> NoteItem | None:
        fields: dict[str, object] = {}
        if text is not None:
            fields["text"] = text
        if checked is not None:
            fields["checked"] = checked
        if not fields:
            return await self._items.get(item_id)
        return await self._items.update(item_id, **fields)

    async def toggle_item(self, item_id: int) -> NoteItem | None:
        item = await self._items.get(item_id)
        if item is None:
            return None
        return await self._items.update(item_id, checked=not item.checked)

    async def delete_item(self, item_id: int) -> bool:
        return await self._items.delete(item_id)
