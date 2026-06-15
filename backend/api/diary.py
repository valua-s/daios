from __future__ import annotations

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, post
from litestar.exceptions import ClientException, NotFoundException

from backend.api.schemas import CreateDiaryEntryRequest, DiaryEntryDTO
from backend.models.diary import DiaryEntry
from backend.services.diary_service import DiaryService


def _to_dto(entry: DiaryEntry) -> DiaryEntryDTO:
    return DiaryEntryDTO(
        id=entry.id,
        kind=entry.kind,
        content=entry.content,
        created_at=entry.created_at,
    )


class DiaryController(Controller):
    path = "/api/diary"

    @get("/")
    async def list_entries(self, diary_service: FromDishka[DiaryService]) -> list[DiaryEntryDTO]:  # noqa: PLR6301
        entries = await diary_service.list_entries()
        return [_to_dto(e) for e in entries]

    @post("/")
    async def create_entry(  # noqa: PLR6301
        self,
        data: CreateDiaryEntryRequest,
        diary_service: FromDishka[DiaryService],
    ) -> DiaryEntryDTO:
        content = data.content.strip()
        if not content:
            raise ClientException(detail="Empty diary entry")
        entry = await diary_service.create_entry(content, data.kind)
        return _to_dto(entry)

    @delete("/{entry_id:int}")
    async def delete_entry(  # noqa: PLR6301
        self,
        entry_id: int,
        diary_service: FromDishka[DiaryService],
    ) -> None:
        ok = await diary_service.delete_entry(entry_id)
        if not ok:
            raise NotFoundException(detail=f"Diary entry {entry_id} not found")
