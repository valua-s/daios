from __future__ import annotations

from datetime import date

from sqlalchemy import select

from backend.models.task import Task, TaskStatus
from backend.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def get_by_date(self, target_date: date) -> list[Task]:
        result = await self._session.execute(
            select(Task).where(Task.date == target_date).order_by(Task.priority.desc())
        )
        return list(result.scalars().all())

    async def get_pending_by_date(self, target_date: date) -> list[Task]:
        result = await self._session.execute(
            select(Task).where(
                Task.date == target_date,
                Task.status == TaskStatus.pending,
            )
        )
        return list(result.scalars().all())

    async def mark_done(self, task_id: int) -> Task | None:
        return await self.update(task_id, status=TaskStatus.done)
