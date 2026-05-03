# Alembic должен видеть все модели для автогенерации миграций
from __future__ import annotations

from backend.auth.models.user import User
from backend.models.backlog import BacklogItem
from backend.models.base import Base
from backend.models.content import ContentItem
from backend.models.focus import Focus
from backend.models.note import Note, NoteItem
from backend.models.schedule import Schedule
from backend.models.settings import UserSetting
from backend.models.task import Task
from backend.models.workout_cache import WorkoutCache

__all__ = [
    "BacklogItem",
    "Base",
    "ContentItem",
    "Focus",
    "Note",
    "NoteItem",
    "Schedule",
    "Task",
    "User",
    "UserSetting",
    "WorkoutCache",
]
