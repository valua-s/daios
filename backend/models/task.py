from __future__ import annotations

import enum
from datetime import date, time

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Enum, Index, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class TaskStatus(enum.StrEnum):
    pending = "pending"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(enum.StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskSource(enum.StrEnum):
    telegram = "telegram"
    web = "web"
    backlog = "backlog"


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
    scheduled_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    scheduled_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    source: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "source IS NULL OR source IN ('telegram', 'web', 'backlog')",
            name="source",
        ),
        Index("ix_tasks_scheduled_date_status", "scheduled_date", "status"),
    )
