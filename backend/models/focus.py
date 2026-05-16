from __future__ import annotations

import enum

from sqlalchemy import Enum, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class FocusPeriod(str, enum.Enum):
    week = "week"
    month = "month"


class Focus(Base):
    __tablename__ = "focus"

    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[FocusPeriod] = mapped_column(Enum(FocusPeriod), nullable=False)
    # Идентификатор периода: "2025-W12" для недели, "2025-03" для месяца
    period_key: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("period", "period_key", name="uq_focus_period_period_key"),
    )
