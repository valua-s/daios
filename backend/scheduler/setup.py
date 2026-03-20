from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from scheduler.jobs import (
    job_evening_summary,
    job_morning_brief,
    job_workout_reminder,
)

logger = logging.getLogger(__name__)

# Часовой пояс — поменяй на свой если нужно
TIMEZONE = "Asia/Almaty"


def create_scheduler() -> AsyncIOScheduler:
    """Создать и настроить планировщик.

    Расписание здесь — дефолтное. В v1 будет браться из таблицы schedules в БД.
    """
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    scheduler.add_job(
        job_morning_brief,
        trigger=CronTrigger(hour=6, minute=30, timezone=TIMEZONE),
        id="morning_brief",
        name="Утренняя сводка",
        replace_existing=True,
    )
    scheduler.add_job(
        job_workout_reminder,
        trigger=CronTrigger(hour=17, minute=30, timezone=TIMEZONE),
        id="workout_reminder",
        name="Напоминание о тренировке",
        replace_existing=True,
    )
    scheduler.add_job(
        job_evening_summary,
        trigger=CronTrigger(hour=22, minute=0, timezone=TIMEZONE),
        id="evening_summary",
        name="Вечерний итог",
        replace_existing=True,
    )

    logger.info("Scheduler configured: %d jobs", len(scheduler.get_jobs()))
    return scheduler
