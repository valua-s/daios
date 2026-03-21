from __future__ import annotations

import asyncio
import logging
import ssl

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand
from dishka import make_async_container
from dishka.integrations.aiogram import setup_dishka

from backend.bot.handlers import common, focus, tasks, workout
from backend.bot.middlewares.owner_only import OwnerOnlyMiddleware
from backend.core.config import settings
from backend.core.providers import AppProvider
from backend.core.redis import redis_client

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


def create_bot() -> Bot:
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    session = AiohttpSession(
        connector=aiohttp.TCPConnector,
        connector_kwargs={"ssl": ssl_context},
    )
    return Bot(
        token=settings.telegram_bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    storage = RedisStorage(redis=redis_client)
    dp = Dispatcher(storage=storage)

    container = make_async_container(AppProvider())
    setup_dishka(container, dp)
    dp.message.middleware(OwnerOnlyMiddleware())
    dp.callback_query.middleware(OwnerOnlyMiddleware())

    dp.include_router(common.router)
    dp.include_router(focus.router)
    dp.include_router(tasks.router)
    dp.include_router(workout.router)

    return dp


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info("Starting DAIOS bot...")

    bot = create_bot()
    dp = create_dispatcher()

    await bot.set_my_commands(BOT_COMMANDS)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())