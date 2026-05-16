from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)

    items: Mapped[list[NoteItem]] = relationship(
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="NoteItem.sort_order",
        lazy="selectin",
        passive_deletes=True,
    )


class NoteItem(Base):
    __tablename__ = "note_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    note_id: Mapped[int] = mapped_column(
        ForeignKey("notes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    note: Mapped[Note] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint("note_id", "sort_order", name="uq_note_items_note_id_sort_order"),
    )
