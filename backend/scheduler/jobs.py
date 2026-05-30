from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dishka import AsyncContainer

from backend.agents.orchestrator import Orchestrator
from backend.integrations.telegram import TelegramNotifier
from backend.services.content_service import ContentService
from backend.services.focus_resolver import FocusResolver
from backend.services.llm_service import LLMService
from backend.services.task_service import TaskService
from backend.services.workout_service import WorkoutService

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


def make_collect_content(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running collect_content")
        async with container() as request_container:
            svc = await request_container.get(ContentService)
            rss = await svc.collect_rss()
            yt = await svc.collect_youtube()
            vk = await svc.collect_vk()
            news = await svc.collect_news()
            logger.info("Content collected: rss=%d yt=%d vk=%d news=%d", rss, yt, vk, news)

            # Динамический сбор по LLM-запросам
            try:
                llm = await request_container.get(LLMService)
                resolver = await request_container.get(FocusResolver)
                focus = await resolver.resolve()
                queries = await llm.generate_search_queries(focus.description, focus.topics)
                dynamic = await svc.collect_dynamic(queries)
                logger.info(
                    "Dynamic content collected: %d items from %d queries (focus: %s)",
                    dynamic, len(queries), focus.source,
                )
            except Exception:
                logger.exception("Dynamic content collection failed, continuing with static only")

    return job


def make_morning_brief(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running morning_brief")
        async with container() as request_container:
            orchestrator = await request_container.get(Orchestrator)
            await orchestrator.run(state={})

    return job


def make_sync_workouts(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running sync_workouts")
        async with container() as request_container:
            svc = await request_container.get(WorkoutService)
            count = await svc.sync_week()
            logger.info("sync_workouts done: %d days synced", count)

    return job


def make_evening_summary(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running evening_summary")
        async with container() as request_container:
            orchestrator = await request_container.get(Orchestrator)
            await orchestrator.run_evening(state={})

    return job


def make_midnight_backlog(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running midnight_backlog")
        async with container() as request_container:
            svc = await request_container.get(TaskService)
            count = await svc.move_pending_to_backlog()
            logger.info("Moved %d pending tasks to backlog", count)

    return job


def make_evening_brief(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running evening_brief")
        async with container() as request_container:
            orchestrator = await request_container.get(Orchestrator)
            await orchestrator.run_evening_brief(state={})

    return job


def make_tasks_reminder(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running tasks_reminder")
        async with container() as request_container:
            task_service = await request_container.get(TaskService)
            notifier = await request_container.get(TelegramNotifier)
            tasks = await task_service.get_today_tasks()
            if tasks:
                logger.info("tasks_reminder skipped: %d tasks already exist", len(tasks))
                return
            await notifier.send(
                "📝 На сегодня ещё нет задач — самое время запланировать день"
            )

    return job
