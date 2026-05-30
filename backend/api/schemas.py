from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import time


@dataclass
class TaskDTO:
    id: int
    title: str
    status: str
    priority: str
    scheduled_date: date
    scheduled_time: time | None
    source: str | None
    notes: str | None


@dataclass
class CreateTaskRequest:
    title: str
    priority: str = "medium"
    source: str = "web"
    scheduled_date: date | None = None
    scheduled_time: time | None = None
    notes: str | None = None


class UpdateTaskRequest(BaseModel):
    model_config = {"from_attributes": True}
    title: str | None = None
    scheduled_date: date | None = None
    scheduled_time: str | None = None
    notes: str | None = None
    clear_time: bool = False
    clear_notes: bool = False


@dataclass
class BacklogItemDTO:
    id: int
    title: str
    reason: str | None
    notes: str | None


@dataclass
class CreateBacklogItemRequest:
    title: str
    reason: str | None = None
    notes: str | None = None


@dataclass
class FocusDTO:
    id: int
    period: str
    period_key: str
    description: str
    is_active: bool


@dataclass
class SetFocusRequest:
    description: str


@dataclass
class NoteItemDTO:
    id: int
    note_id: int
    text: str
    checked: bool
    sort_order: int


@dataclass
class NoteDTO:
    id: int
    title: str
    body: str | None
    items: list[NoteItemDTO]


@dataclass
class CreateNoteRequest:
    title: str
    body: str | None = None


class UpdateNoteRequest(BaseModel):
    model_config = {"from_attributes": True}
    title: str | None = None
    body: str | None = None
    clear_body: bool = False


@dataclass
class CreateNoteItemRequest:
    text: str


class UpdateNoteItemRequest(BaseModel):
    model_config = {"from_attributes": True}
    text: str | None = None
    checked: bool | None = None
