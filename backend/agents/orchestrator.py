from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from backend.agents.base import BaseAgent
from backend.agents.content_agent import ContentAgent
from backend.agents.context_agent import ContextAgent
from backend.agents.evening_agent import EveningAgent
from backend.agents.task_agent import TaskAgent
from backend.agents.workout_agent import WorkoutAgent
from backend.bot.formatters import (
    format_evening_brief,
    format_evening_summary,
    format_morning_brief,
)
from backend.bot.keyboards import (
    evening_postpone_all_keyboard,
    evening_task_keyboard,
)
from backend.core.config import settings
from backend.integrations.telegram import TelegramNotifier
from backend.services.task_service import TaskService

logger = logging.getLogger(__name__)


class Orchestrator(BaseAgent):
    """Управляет утренней и вечерней цепочками агентов."""

    def __init__(
        self,
        context_agent: ContextAgent,
        workout_agent: WorkoutAgent,
        task_agent: TaskAgent,
        content_agent: ContentAgent,
        evening_agent: EveningAgent,
        task_service: TaskService,
        notifier: TelegramNotifier,
    ) -> None:
        self._context = context_agent
        self._workout = workout_agent
        self._tasks = task_agent
        self._content = content_agent
        self._evening = evening_agent
        self._task_service = task_service
        self._notifier = notifier

    async def _run_agents(self, state: dict[str, Any]) -> dict[str, Any]:
        """Запускает агентов последовательно — общая DB-сессия."""
        for agent in (self._context, self._workout, self._tasks, self._content):
            state = await agent.run(state)
        return state

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        """Утренняя сводка: контекст + тренировка + задачи + контент."""
        state = await self._run_agents(state)

        text = self.build_morning_brief(state)
        await self._notifier.send(text)

        return {**state, "morning_brief": text}

    async def run_evening_brief(self, state: dict[str, Any]) -> dict[str, Any]:
        """Вечерняя сводка: контекст + тренировка + задачи + контент."""
        state = await self._run_agents(state)

        text = self.build_evening_brief(state)
        await self._notifier.send(text)

        return {**state, "evening_brief": text}

    async def run_evening(self, state: dict[str, Any]) -> dict[str, Any]:
        """Вечерний итог: анализ задач + перенос невыполненных + отправка."""
        state = await self._evening.run(state)

        done = state.get("done_tasks", [])
        pending = state.get("pending_tasks", [])

        text = format_evening_summary(done, pending)
        await self._notifier.send(text)

        for task in pending:
            time_str = f" · {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
            await self._notifier.send(
                f"⏳ {task.title}{time_str}",
                keyboard=evening_task_keyboard(task.id),
            )

        if pending:
            await self._notifier.send(
                f"👆 {len(pending)} невыполненных — выбери что делать с каждой или перенеси все:",
                keyboard=evening_postpone_all_keyboard(),
            )

        return {**state, "evening_summary": text}

    @staticmethod
    def build_morning_brief(state: dict[str, Any]) -> str:
        all_items = state.get("content_items", [])
        return format_morning_brief(
            today=datetime.now(ZoneInfo(settings.app_timezone)).date(),
            workout=state.get("workout"),
            tasks=state.get("tasks", []),
            weather=state.get("weather"),
            bus_schedule=state.get("bus_schedule", []),
            is_weekend=state.get("is_weekend", False),
            content_items=all_items[:3],
        )

    @staticmethod
    def build_evening_brief(state: dict[str, Any]) -> str:
        all_items = state.get("content_items", [])
        return format_evening_brief(
            today=datetime.now(ZoneInfo(settings.app_timezone)).date(),
            workout=state.get("workout"),
            tasks=state.get("tasks", []),
            bus_schedule=state.get("bus_schedule", []),
            is_weekend=state.get("is_weekend", False),
            content_items=all_items[3:],
        )
