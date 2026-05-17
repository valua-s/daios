from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from dishka import make_async_container
from dishka.integrations.aiogram import setup_dishka

from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.logbot import ioc
from backend.logbot.handlers import logs
from backend.logbot.middlewares import OwnerOnlyMiddleware
from backend.logbot.services.tailer import run_error_tailer

logger = logging.getLogger(__name__)

BOT_COMMANDS = [
    BotCommand(command="tail", description="Хвост лога (default: bot, 50 строк)"),
    BotCommand(command="logs", description="/logs <service> [N]"),
    BotCommand(command="errors", description="Хвост error-логов"),
    BotCommand(command="help", description="Список команд"),
]


async def main() -> None:
    setup_logging("logbot")
    logger.info("Starting DAIOS log bot...")

    if not settings.telegram_logbot_token:
        logger.error("TELEGRAM_LOGBOT_TOKEN is not set; refusing to start")
        return

    async with make_async_container(
        ioc.MainProvider(),
        ioc.AiogramProvider(),
        ioc.SslProvider(),
    ) as container:
        bot = await container.get(Bot, component="aiogram")
        dp = await container.get(Dispatcher, component="aiogram")

        setup_dishka(container, dp)
        dp.message.middleware(OwnerOnlyMiddleware())
        dp.include_routers(logs.router)

        await bot.set_my_commands(BOT_COMMANDS)
        await bot.delete_webhook(drop_pending_updates=True)

        tailer_task = asyncio.create_task(run_error_tailer(bot))
        try:
            await dp.start_polling(bot)
        finally:
            tailer_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
