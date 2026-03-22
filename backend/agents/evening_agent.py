from __future__ import annotations

import logging
from typing import Any

from backend.agents.base import BaseAgent
from backend.models.task import TaskStatus
from backend.services.task_service import TaskService

logger = logging.getLogger(__name__)


class EveningAgent(BaseAgent):
    """Подводит итог дня: делит задачи на выполненные и нет.
    Добавляет в state ключи `done_tasks` и `pending_tasks`.
    """

    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tasks = []

        try:
            tasks = await self._task_service.get_today_tasks()
        except Exception:
            logger.exception("Failed to fetch today tasks for evening summary")

        done = [t for t in tasks if t.status == TaskStatus.done]
        pending = [t for t in tasks if t.status == TaskStatus.pending]

        return {
            **state,
            "done_tasks": done,
            "pending_tasks": pending,
        }
