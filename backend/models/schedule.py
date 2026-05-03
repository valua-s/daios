from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class Schedule(Base):
    """Настраиваемые триггеры автоматизаций."""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Например: "morning_brief", "evening_summary", "content_fetch"
    cron_expr: Mapped[str] = mapped_column(Text, nullable=False)
    # Стандартный cron: "30 6 * * *" = 06:30 каждый день
    cron_expr_weekend: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Если задано — cron_expr применяется только к будням, cron_expr_weekend — к выходным
    enabled: Mapped[bool] = mapped_column(default=True)
    description: Mapped[str | None] = mapped_column(Text)
