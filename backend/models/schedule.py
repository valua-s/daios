from __future__ import annotations

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base

ALLOWED_EVENT_NAMES: tuple[str, ...] = (
    "morning_brief",
    "evening_summary",
    "collect_content",
    "sync_workouts",
    "evening_brief",
    "midnight_backlog",
    "tasks_reminder",
)


class Schedule(Base):
    """Настраиваемые триггеры автоматизаций."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    cron_expr: Mapped[str] = mapped_column(Text, nullable=False)
    # Если задано — cron_expr применяется к будням, cron_expr_weekend — к выходным
    cron_expr_weekend: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "event_name IN ("
            + ", ".join(f"'{n}'" for n in ALLOWED_EVENT_NAMES)
            + ")",
            name="event_name",
        ),
    )
