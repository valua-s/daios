from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.models.backlog import BacklogItem
from backend.models.task import Task, TaskPriority, TaskStatus
from backend.repositories.backlog_repo import BacklogRepository
from backend.repositories.task_repo import TaskRepository


def _today() -> date:
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


class TaskService:
    """Вся бизнес-логика задач и бэклога."""

    def __init__(self, session: AsyncSession) -> None:
        self._tasks: TaskRepository = TaskRepository(session)
        self._backlog = BacklogRepository(session)
        self._session = session

    # ── Задачи ──────────────────────────────────────────────────────────

    async def get_today_tasks(self) -> list[Task]:
        return await self._tasks.get_by_date(_today())

    async def get_pending_today(self) -> list[Task]:
        return await self._tasks.get_pending_by_date(_today())

    async def get_tasks_by_range(
        self, from_date: date, to_date: date
    ) -> list[Task]:
        return await self._tasks.get_by_date_range(from_date, to_date)

    async def get_task(self, task_id: int) -> Task | None:
        return await self._tasks.get(task_id)

    async def create_task(
        self,
        title: str,
        priority: str = "medium",
        source: str = "telegram",
        target_date: date | None = None,
        scheduled_time: time | None = None,
        notes: str | None = None,
    ) -> Task:
        task = await self._tasks.create(
            title=title,
            priority=TaskPriority(priority),
            source=source,
            date=target_date or _today(),
            status=TaskStatus.pending,
            scheduled_time=scheduled_time,
            notes=notes,
        )
        await self._session.commit()
        return task

    async def update_task(
        self,
        task_id: int,
        **kwargs: Any,
    ) -> Task | None:
        updated = await self._tasks.update(task_id, **kwargs)
        if updated:
            await self._session.commit()
        return updated

    async def toggle_task(self, task_id: int) -> Task | None:
        task = await self._tasks.get(task_id)
        if task is None:
            return None
        new_status = (
            TaskStatus.pending if task.status == TaskStatus.done else TaskStatus.done
        )
        updated = await self._tasks.update(task_id, status=new_status)
        await self._session.commit()
        return updated

    async def delete_task(self, task_id: int) -> bool:
        result = await self._tasks.delete(task_id)
        await self._session.commit()
        return result

    async def postpone_task(self, task_id: int) -> Task | None:
        updated = await self._tasks.update(
            task_id,
            date=_today() + timedelta(days=1),
            status=TaskStatus.pending,
        )
        await self._session.commit()
        return updated

    async def postpone_pending_to_tomorrow(self) -> int:
        """Переносит все невыполненные задачи на сегодня на завтра.
        Возвращает количество перенесённых задач.
        """
        pending = await self._tasks.get_pending_by_date(_today())
        tomorrow = _today() + timedelta(days=1)
        for task in pending:
            await self._tasks.update(task.id, date=tomorrow)
        await self._session.commit()
        return len(pending)

    async def move_to_backlog(self, task_id: int) -> bool:
        task = await self._tasks.get(task_id)
        if task is None:
            return False
        await self._backlog.create(
            title=task.title,
            reason="перенесено из задач дня",
            notes=task.notes,
        )
        await self._tasks.delete(task_id)
        await self._session.commit()
        return True

    # ── Бэклог ──────────────────────────────────────────────────────────

    async def get_backlog(self) -> list[BacklogItem]:
        return await self._backlog.get_all_ordered()

    async def move_from_backlog_to_today(self, item_id: int) -> Task | None:
        item = await self._backlog.get(item_id)
        if item is None:
            return None
        task = await self._tasks.create(
            title=item.title,
            date=_today(),
            source="backlog",
            priority=TaskPriority.medium,
            status=TaskStatus.pending,
        )
        await self._backlog.delete(item_id)
        await self._session.commit()
        return task

    async def delete_backlog_item(self, item_id: int) -> bool:
        result = await self._backlog.delete(item_id)
        await self._session.commit()
        return result
