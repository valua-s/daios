from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka import AsyncContainer, make_async_container
from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.providers import AppProvider
from backend.scheduler.jobs import (
    make_collect_content,
    make_evening_brief,
    make_evening_summary,
    make_morning_brief,
    make_sync_workouts,
)
from backend.services.settings_service import SettingsService

logger = logging.getLogger(__name__)

SCHEDULE_RELOAD_CHANNEL = "schedule:reload"

# Маппинг event_name → фабрика job-функции
JOB_FACTORIES: dict[str, Callable[[AsyncContainer], Callable]] = {
    "morning_brief": make_morning_brief,
    "evening_summary": make_evening_summary,
    "collect_content": make_collect_content,
    "sync_workouts": make_sync_workouts,
    "evening_brief": make_evening_brief
}


def _parse_cron(cron_expr: str) -> list[CronTrigger]:
    """Парсит cron выражение в список триггеров.

    Поддерживает мульти-значения (напр. '0 6,17 * * *' → 2 триггера).
    """
    parts = cron_expr.split()
    minute, hours_str = parts[0], parts[1]
    return [
        CronTrigger(
            hour=int(hour),
            minute=int(minute),
            timezone=settings.app_timezone,
        )
        for hour in hours_str.split(",")
    ]


async def load_schedules_from_db(container: AsyncContainer) -> list[dict]:
    """Читает расписания из БД, создавая дефолты если нужно."""
    async with container() as req:
        svc = await req.get(SettingsService)
        await svc.ensure_default_schedules()
        return [
            {
                "event_name": s.event_name,
                "cron_expr": s.cron_expr,
                "enabled": s.enabled,
            }
            for s in await svc.get_schedules()
        ]


def apply_schedules(
    scheduler: AsyncIOScheduler,
    container: AsyncContainer,
    schedules: list[dict],
) -> None:
    """Применяет расписания к планировщику."""
    # Удаляем все текущие джобы
    for job in scheduler.get_jobs():
        job.remove()

    for s in schedules:
        factory = JOB_FACTORIES.get(s["event_name"])
        if factory is None:
            logger.warning("Unknown event_name: %s, skipping", s["event_name"])
            continue
        if not s["enabled"]:
            logger.info("Schedule %s disabled, skipping", s["event_name"])
            continue

        job_func = factory(container)
        triggers = _parse_cron(s["cron_expr"])

        for i, trigger in enumerate(triggers):
            job_id = s["event_name"] if len(triggers) == 1 else f"{s['event_name']}_{i:02d}"
            scheduler.add_job(
                job_func,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
            )

    logger.info("Schedules applied. Jobs: %s", [j.id for j in scheduler.get_jobs()])


async def listen_for_reload(
    redis: Redis,
    scheduler: AsyncIOScheduler,
    container: AsyncContainer,
) -> None:
    """Слушает Redis pub/sub для hot-reload расписаний."""
    pubsub = redis.pubsub()
    await pubsub.subscribe(SCHEDULE_RELOAD_CHANNEL)
    logger.info("Listening for schedule reload on channel '%s'", SCHEDULE_RELOAD_CHANNEL)

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        logger.info("Received schedule reload signal")
        try:
            schedules = await load_schedules_from_db(container)
            apply_schedules(scheduler, container, schedules)
        except Exception:
            logger.exception("Failed to reload schedules")


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting DAIOS scheduler...")

    container = make_async_container(AppProvider())
    redis: Redis = await container.get(Redis)

    scheduler = AsyncIOScheduler(timezone=settings.app_timezone)

    # Загружаем расписания из БД
    schedules = await load_schedules_from_db(container)
    apply_schedules(scheduler, container, schedules)

    scheduler.start()

    # Немедленная синхронизация тренировок при старте
    logger.info("Running initial workout sync...")
    await make_sync_workouts(container)()

    # Запускаем слушатель Redis для hot-reload
    reload_task = asyncio.create_task(listen_for_reload(redis, scheduler, container))

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        reload_task.cancel()
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
