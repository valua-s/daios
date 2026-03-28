from __future__ import annotations

from datetime import date

from sqlalchemy import case, select

from backend.models.task import Task, TaskPriority, TaskStatus
from backend.repositories.base import BaseRepository

_PRIORITY_ORDER = case(
    (Task.priority == TaskPriority.high, 0),
    (Task.priority == TaskPriority.medium, 1),
    (Task.priority == TaskPriority.low, 2),
    else_=3,
)


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def get_by_date(self, target_date: date) -> list[Task]:
        result = await self._session.execute(
            select(Task).where(Task.date == target_date).order_by(_PRIORITY_ORDER)
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

    async def get_by_date_range(
        self, from_date: date, to_date: date
    ) -> list[Task]:
        result = await self._session.execute(
            select(Task)
            .where(Task.date >= from_date, Task.date <= to_date)
            .order_by(Task.date, _PRIORITY_ORDER)
        )
        return list(result.scalars().all())

    async def mark_done(self, task_id: int) -> Task | None:
        return await self.update(task_id, status=TaskStatus.done)
