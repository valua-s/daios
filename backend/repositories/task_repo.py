from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import case, select, update

from backend.models.task import Task, TaskPriority, TaskStatus
from backend.repositories.base import BaseRepository

if TYPE_CHECKING:
    from datetime import date

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
            select(Task).where(Task.scheduled_date == target_date).order_by(_PRIORITY_ORDER)
        )
        return list(result.scalars().all())

    async def get_pending_by_date(self, target_date: date) -> list[Task]:
        result = await self._session.execute(
            select(Task).where(
                Task.scheduled_date == target_date,
                Task.status == TaskStatus.pending,
            )
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self, from_date: date, to_date: date
    ) -> list[Task]:
        result = await self._session.execute(
            select(Task)
            .where(Task.scheduled_date >= from_date, Task.scheduled_date <= to_date)
            .order_by(Task.scheduled_date, _PRIORITY_ORDER)
        )
        return list(result.scalars().all())

    async def get_overdue_pending(self, today: date) -> list[Task]:
        result = await self._session.execute(
            select(Task).where(
                Task.scheduled_date < today,
                Task.status == TaskStatus.pending,
            )
        )
        return list(result.scalars().all())

    async def mark_done(self, task_id: int) -> Task | None:
        return await self.update(task_id, status=TaskStatus.done)

    async def bulk_postpone(self, from_date: date, to_date: date) -> int:
        """Переносит все pending-задачи с from_date на to_date. Возвращает кол-во."""
        result = await self._session.execute(
            update(Task)
            .where(Task.scheduled_date == from_date, Task.status == TaskStatus.pending)
            .values(scheduled_date=to_date)
        )
        return result.rowcount
