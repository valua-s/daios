from __future__ import annotations

import asyncio
import logging
import signal
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka import AsyncContainer, make_async_container
from redis.asyncio import Redis

from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.core.providers import AppProvider
from backend.scheduler.jobs import (
    make_collect_content,
    make_evening_brief,
    make_evening_summary,
    make_midnight_backlog,
    make_morning_brief,
    make_sync_workouts,
    make_tasks_reminder,
)
from backend.services.settings_service import (
    SCHEDULE_RELOAD_CHANNEL,
    SettingsService,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)

_CRON_FIELDS_COUNT = 5

# Маппинг event_name → фабрика job-функции
JOB_FACTORIES: dict[str, Callable[[AsyncContainer], Callable]] = {
    "morning_brief": make_morning_brief,
    "evening_summary": make_evening_summary,
    "collect_content": make_collect_content,
    "sync_workouts": make_sync_workouts,
    "evening_brief": make_evening_brief,
    "midnight_backlog": make_midnight_backlog,
    "tasks_reminder": make_tasks_reminder,
}


def _parse_cron(cron_expr: str, dow_override: str | None = None) -> list[CronTrigger]:
    """Парсит cron выражение в список триггеров.

    Поддерживает мульти-значения (напр. '0 6,17 * * *' → 2 триггера)
    и day-of-week (напр. '30 6 * * 1-5'). Если задан `dow_override` —
    перекрывает dow из выражения (используется для weekday/weekend сплита).
    """
    parts = cron_expr.split()
    if len(parts) < _CRON_FIELDS_COUNT:
        msg = f"Invalid cron expression: {cron_expr!r}"
        raise ValueError(msg)
    minute, hours_str, dom, month, dow = parts[:5]
    kwargs: dict[str, str | int] = {"timezone": settings.app_timezone}
    if dom != "*":
        kwargs["day"] = dom
    if month != "*":
        kwargs["month"] = month
    effective_dow = dow_override if dow_override is not None else (dow if dow != "*" else None)
    if effective_dow is not None:
        kwargs["day_of_week"] = effective_dow
    return [
        CronTrigger(
            hour=int(hour),
            minute=int(minute),
            **kwargs,
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
                "cron_expr_weekend": s.cron_expr_weekend,
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
        cron_we = s.get("cron_expr_weekend")
        if cron_we:
            # Сплит: будни → cron_expr, выходные → cron_expr_weekend
            groups = [
                ("wd", _parse_cron(s["cron_expr"], dow_override="mon-fri")),
                ("we", _parse_cron(cron_we, dow_override="sat,sun")),
            ]
        else:
            groups = [("", _parse_cron(s["cron_expr"]))]

        for suffix, triggers in groups:
            for i, trigger in enumerate(triggers):
                base = s["event_name"] if not suffix else f"{s['event_name']}_{suffix}"
                job_id = base if len(triggers) == 1 else f"{base}_{i:02d}"
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
    setup_logging("scheduler")
    logger.info("Starting DAIOS scheduler...")

    container = make_async_container(AppProvider())
    redis: Redis = await container.get(Redis)

    scheduler = AsyncIOScheduler(
        timezone=settings.app_timezone,
        job_defaults={"misfire_grace_time": 1, "coalesce": True},
    )

    # Загружаем расписания из БД
    schedules = await load_schedules_from_db(container)
    apply_schedules(scheduler, container, schedules)

    scheduler.start()

    # Немедленная синхронизация тренировок при старте
    logger.info("Running initial workout sync...")
    await make_sync_workouts(container)()

    # Запускаем слушатель Redis для hot-reload
    reload_task = asyncio.create_task(listen_for_reload(redis, scheduler, container))

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        reload_task.cancel()
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
