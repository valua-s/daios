from __future__ import annotations

import logging
from collections.abc import Callable

from dishka import AsyncContainer

from backend.agents.orchestrator import Orchestrator
from backend.services.content_service import ContentService
from backend.services.workout_service import WorkoutService

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


def make_evening_brief(container: AsyncContainer) -> Callable:
    async def job() -> None:
        logger.info("Running evening_brief")
        async with container() as request_container:
            orchestrator = await request_container.get(Orchestrator)
            await orchestrator.run_evening_brief(state={})

    return job