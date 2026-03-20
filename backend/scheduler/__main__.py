import asyncio
import logging
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from dishka import make_async_container

from backend.core.providers import AppProvider
from backend.scheduler.jobs import make_collect_content, make_evening_summary, make_morning_brief, make_sync_workouts

logger = logging.getLogger(__name__)

TIMEZONE = "Europe/Moscow"


def create_scheduler(container: Any) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)

    sync_workouts_job = make_sync_workouts(container)

    # 06:00, 17:00 — синхронизация тренировок из Google Sheets в DB
    for hour in (6, 17):
        scheduler.add_job(
            sync_workouts_job,
            trigger=CronTrigger(hour=hour, minute=0, timezone=TIMEZONE),
            id=f"sync_workouts_{hour:02d}",
            replace_existing=True,
        )

    # 06:00 — сбор контента (до утренней сводки)
    scheduler.add_job(
        make_collect_content(container),
        trigger=CronTrigger(hour=6, minute=0, timezone=TIMEZONE),
        id="collect_content",
        replace_existing=True,
    )

    # 06:30 — утренняя сводка: погода + автобусы + тренировка + задачи + контент
    scheduler.add_job(
        make_morning_brief(container),
        trigger=CronTrigger(hour=6, minute=30, timezone=TIMEZONE),
        id="morning_brief",
        replace_existing=True,
    )

    # 09:00 — задачи дня (заглушка, Фаза 3)
    scheduler.add_job(
        make_morning_brief(container),  # временно — та же сводка
        trigger=CronTrigger(hour=9, minute=0, timezone=TIMEZONE),
        id="tasks_morning",
        replace_existing=True,
    )

    # 17:30 — вечерняя тренировка + учёба (заглушка, Фаза 3)
    scheduler.add_job(
        make_evening_summary(container),
        trigger=CronTrigger(hour=17, minute=30, timezone=TIMEZONE),
        id="evening_workout",
        replace_existing=True,
    )

    # 22:00 — итог дня
    scheduler.add_job(
        make_evening_summary(container),
        trigger=CronTrigger(hour=22, minute=0, timezone=TIMEZONE),
        id="evening_summary",
        replace_existing=True,
    )

    return scheduler


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting DAIOS scheduler...")

    container = make_async_container(AppProvider())
    scheduler = create_scheduler(container)
    scheduler.start()

    logger.info("Scheduler running. Jobs: %s", [j.id for j in scheduler.get_jobs()])

    # Немедленная синхронизация тренировок при старте
    logger.info("Running initial workout sync...")
    await make_sync_workouts(container)()

    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())