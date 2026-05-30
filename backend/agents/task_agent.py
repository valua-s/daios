from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.agents.base import BaseAgent
from backend.services.task_service import TaskService

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class TaskAgent(BaseAgent):
    """Получает задачи на сегодня и добавляет их в state.

    Добавляет ключ `tasks` в state.
    """

    def __init__(self, task_service: TaskService) -> None:
        self._task_service = task_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tasks = []

        try:
            tasks = await self._task_service.get_today_tasks()
        except Exception:
            logger.exception("Failed to fetch today tasks")

        return {
            **state,
            "tasks": tasks,
        }
