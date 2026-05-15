from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, DateTime, Float, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class CompletedWorkout(Base):
    """Фактически выполненная беговая тренировка (источник — Strava)."""

    __tablename__ = "completed_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    strava_activity_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    workout_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    distance_km_override: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    @property
    def effective_distance_km(self) -> float:
        return self.distance_km_override if self.distance_km_override is not None else self.distance_km
