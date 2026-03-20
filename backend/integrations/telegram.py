from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup

from backend.core.config import settings
from backend.integrations.base import BaseIntegration


class TelegramNotifier(BaseIntegration):
    """Отправляет сообщения владельцу бота.
    Используется агентами и планировщиком — не хендлерами.
    Хендлеры работают с Bot напрямую через aiogram.
    """

    def __init__(self) -> None:
        self._bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self._user_id = settings.telegram_user_id

    async def send(
        self,
        text: str,
        keyboard: InlineKeyboardMarkup | None = None,
    ) -> None:
        await self._bot.send_message(
            chat_id=self._user_id,
            text=text,
            reply_markup=keyboard,
        )

    async def close(self) -> None:
        await self._bot.session.close()
