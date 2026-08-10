from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from backend.agents.base import BaseAgent
from backend.models.task import TaskStatus
from backend.services.stats_service import StatsService
from backend.services.task_service import TaskService

if TYPE_CHECKING:
    from typing import Any

logger = logging.getLogger(__name__)


class EveningAgent(BaseAgent):
    """Подводит итог дня: делит задачи на выполненные и нет.

    Добавляет в state ключи `done_tasks`, `pending_tasks` и `day_stats`.
    """

    def __init__(
        self, task_service: TaskService, stats_service: StatsService
    ) -> None:
        self._task_service = task_service
        self._stats_service = stats_service

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        tasks = []

        try:
            tasks = await self._task_service.get_today_tasks()
        except Exception:
            logger.exception("Failed to fetch today tasks for evening summary")

        done = [t for t in tasks if t.status == TaskStatus.done]
        pending = [t for t in tasks if t.status == TaskStatus.pending]

        day_stats = None
        try:
            day_stats = await self._stats_service.get_day_stats()
        except Exception:
            logger.exception("Failed to collect day stats for evening summary")

        return {
            **state,
            "done_tasks": done,
            "pending_tasks": pending,
            "day_stats": day_stats,
        }
