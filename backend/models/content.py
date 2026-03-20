from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


class ContentType(str, enum.Enum):
    article = "article"
    video = "video"
    podcast = "podcast"


class ContentStatus(str, enum.Enum):
    new = "new"
    queued = "queued"   # отобран для показа сегодня
    shown = "shown"     # уже показан пользователю
    saved = "saved"     # пользователь сохранил


class ContentItem(Base):
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[ContentType] = mapped_column(Enum(ContentType), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str | None] = mapped_column(Text, index=True)  # python | ai | running | economics
    source: Mapped[str | None] = mapped_column(Text)             # rss | youtube | vk | telegram
    status: Mapped[ContentStatus] = mapped_column(
        Enum(ContentStatus), default=ContentStatus.new, index=True
    )
    minio_key: Mapped[str | None] = mapped_column(Text)          # путь в Minio если скачан
    shown_at: Mapped[datetime | None] = mapped_column(DateTime)
    duration_minutes: Mapped[int | None] = mapped_column()       # для видео/подкастов
