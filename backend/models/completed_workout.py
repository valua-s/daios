from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from sqlalchemy import Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CompletedWorkout(Base):
    """Факт выполненной тренировки — заполняется вручную пользователем."""

    __tablename__ = "completed_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_date: Mapped[date] = mapped_column(sa.Date, nullable=False, unique=True, index=True)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
