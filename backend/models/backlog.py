from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class BacklogItem(Base):
    __tablename__ = "backlog"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)  # почему отложено
    notes: Mapped[str | None] = mapped_column(Text)
