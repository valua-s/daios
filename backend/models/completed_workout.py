from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import BigInteger, Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base

SOURCE_MANUAL = "manual"
SOURCE_STRAVA = "strava"


class CompletedWorkout(Base):
    """Факт выполненной тренировки: ручная отметка или активность из Strava.

    За один день может быть несколько записей — тренировки разных типов
    проводятся в разное время и учитываются раздельно.
    """

    __tablename__ = "completed_workouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    workout_date: Mapped[date] = mapped_column(sa.Date, nullable=False, index=True)
    activity_type: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    distance_km: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False, default=SOURCE_MANUAL)
    strava_activity_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True, unique=True, index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime, nullable=True)

    __table_args__ = (
        sa.Index(
            "uq_completed_workouts_manual_date_type",
            "workout_date",
            "activity_type",
            unique=True,
            postgresql_where=sa.text(f"source = '{SOURCE_MANUAL}'"),
        ),
    )
