from __future__ import annotations

from dataclasses import dataclass
from datetime import date as data, time

from pydantic import BaseModel


@dataclass
class TaskDTO:
    id: int
    title: str
    status: str
    priority: str
    date: data
    scheduled_time: time | None
    source: str | None
    notes: str | None


@dataclass
class CreateTaskRequest:
    title: str
    priority: str = "medium"
    source: str = "web"
    date: data | None = None
    scheduled_time: time | None = None
    notes: str | None = None


class UpdateTaskRequest(BaseModel):
    model_config = {"from_attributes": True}
    title: str | None = None
    date: data | None = None
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
