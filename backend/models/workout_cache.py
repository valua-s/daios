from __future__ import annotations

from datetime import date as data, datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class WorkoutCache(Base):
    """Кэш тренировок из Google Sheets — не ходим в Sheets при каждом запросе."""

    __tablename__ = "workout_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[data] = mapped_column(sa.Date, nullable=False, unique=True, index=True)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON со структурой тренировки
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
