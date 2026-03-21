from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dishka import make_async_container
from dishka.integrations.aiogram import setup_dishka

from backend.bot import ioc
from backend.bot.handlers import common, focus, tasks, workout
from backend.bot.middlewares.owner_only import OwnerOnlyMiddleware
from backend.core.providers import AppProvider

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="tasks", description="Задачи на сегодня"),
    BotCommand(command="addtask", description="Добавить задачу"),
    BotCommand(command="backlog", description="Задачи без срока"),
    BotCommand(command="workout", description="Тренировка на сегодня"),
    BotCommand(command="morning", description="Утренняя сводка прямо сейчас"),
    BotCommand(command="focus", description="Текущий фокус недели и месяца"),
    BotCommand(command="help", description="Список команд"),
]


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting DAIOS bot...")

    async with make_async_container(
        AppProvider(),
        ioc.MainProvider(),
        ioc.AiogramProvider(),
        ioc.SslProvider(),
    ) as container:
        bot = await container.get(Bot, component="aiogram")
        dp = await container.get(Dispatcher, component="aiogram")

        setup_dishka(container, dp)
        dp.message.middleware(OwnerOnlyMiddleware())
        dp.callback_query.middleware(OwnerOnlyMiddleware())

        dp.include_router(common.router)
        dp.include_router(focus.router)
        dp.include_router(tasks.router)
        dp.include_router(workout.router)

        await bot.set_my_commands(BOT_COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
