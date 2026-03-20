from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class UserSetting(Base):
    """Key-value хранилище пользовательских настроек."""

    __tablename__ = "user_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    # Примеры ключей:
    # "interests.python" = "true"
    # "interests.politics" = "false"
    # "workout.pace_min_per_km" = "6.0"
    # "workout.strength_session_minutes" = "60"
