from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.diary import DiaryEntry
from backend.repositories.diary_repo import DiaryRepository

KIND_TEXT = "text"
KIND_VOICE = "voice"


class DiaryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._entries = DiaryRepository(session)

    async def list_entries(self) -> list[DiaryEntry]:
        return await self._entries.get_all_ordered()

    async def create_entry(self, content: str, kind: str) -> DiaryEntry:
        normalized = kind if kind in {KIND_TEXT, KIND_VOICE} else KIND_TEXT
        return await self._entries.create(kind=normalized, content=content)

    async def delete_entry(self, entry_id: int) -> bool:
        return await self._entries.delete(entry_id)
