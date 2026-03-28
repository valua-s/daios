from __future__ import annotations

import enum
from datetime import date as data, time

from sqlalchemy import Date, Enum, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TaskStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), default=TaskStatus.pending
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority), default=TaskPriority.medium
    )
    date: Mapped[data] = mapped_column(Date, nullable=False, index=True)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    source: Mapped[str | None] = mapped_column(Text)  # telegram | web | backlog
    notes: Mapped[str | None] = mapped_column(Text)
