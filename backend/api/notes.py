from __future__ import annotations

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, patch, post
from litestar.exceptions import NotFoundException

from backend.api.schemas import (
    CreateNoteItemRequest,
    CreateNoteRequest,
    NoteDTO,
    NoteItemDTO,
    UpdateNoteItemRequest,
    UpdateNoteRequest,
)
from backend.models.note import Note, NoteItem
from backend.services.note_service import NoteService


def _item_to_dto(item: NoteItem) -> NoteItemDTO:
    return NoteItemDTO(
        id=item.id,
        note_id=item.note_id,
        text=item.text,
        checked=item.checked,
        sort_order=item.sort_order,
    )


def _note_to_dto(note: Note) -> NoteDTO:
    return NoteDTO(
        id=note.id,
        title=note.title,
        body=note.body,
        items=[_item_to_dto(i) for i in note.items],
    )


class NotesController(Controller):
    path = "/api/notes"

    @get("/")
    async def list_notes(self, note_service: FromDishka[NoteService]) -> list[NoteDTO]:
        notes = await note_service.list_notes()
        return [_note_to_dto(n) for n in notes]

    @post("/")
    async def create_note(
        self,
        data: CreateNoteRequest,
        note_service: FromDishka[NoteService],
    ) -> NoteDTO:
        note = await note_service.create_note(title=data.title, body=data.body)
        return _note_to_dto(note)

    @get("/{note_id:int}")
    async def get_note(
        self,
        note_id: int,
        note_service: FromDishka[NoteService],
    ) -> NoteDTO:
        note = await note_service.get_note(note_id)
        if note is None:
            raise NotFoundException(detail=f"Note {note_id} not found")
        return _note_to_dto(note)

    @patch("/{note_id:int}")
    async def update_note(
        self,
        note_id: int,
        data: UpdateNoteRequest,
        note_service: FromDishka[NoteService],
    ) -> NoteDTO:
        note = await note_service.update_note(
            note_id,
            title=data.title,
            body=data.body,
            clear_body=data.clear_body,
        )
        if note is None:
            raise NotFoundException(detail=f"Note {note_id} not found")
        return _note_to_dto(note)

    @delete("/{note_id:int}")
    async def delete_note(
        self,
        note_id: int,
        note_service: FromDishka[NoteService],
    ) -> None:
        ok = await note_service.delete_note(note_id)
        if not ok:
            raise NotFoundException(detail=f"Note {note_id} not found")

    @post("/{note_id:int}/items")
    async def add_item(
        self,
        note_id: int,
        data: CreateNoteItemRequest,
        note_service: FromDishka[NoteService],
    ) -> NoteItemDTO:
        item = await note_service.add_item(note_id, data.text)
        if item is None:
            raise NotFoundException(detail=f"Note {note_id} not found")
        return _item_to_dto(item)

    @patch("/items/{item_id:int}")
    async def update_item(
        self,
        item_id: int,
        data: UpdateNoteItemRequest,
        note_service: FromDishka[NoteService],
    ) -> NoteItemDTO:
        item = await note_service.update_item(
            item_id, text=data.text, checked=data.checked
        )
        if item is None:
            raise NotFoundException(detail=f"Note item {item_id} not found")
        return _item_to_dto(item)

    @post("/items/{item_id:int}/toggle")
    async def toggle_item(
        self,
        item_id: int,
        note_service: FromDishka[NoteService],
    ) -> NoteItemDTO:
        item = await note_service.toggle_item(item_id)
        if item is None:
            raise NotFoundException(detail=f"Note item {item_id} not found")
        return _item_to_dto(item)

    @delete("/items/{item_id:int}")
    async def delete_item(
        self,
        item_id: int,
        note_service: FromDishka[NoteService],
    ) -> None:
        ok = await note_service.delete_item(item_id)
        if not ok:
            raise NotFoundException(detail=f"Note item {item_id} not found")
