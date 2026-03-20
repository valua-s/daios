from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from backend.core.config import settings


class OwnerOnlyMiddleware(BaseMiddleware):
    """Отклоняет все сообщения не от владельца.
    DAIOS — персональный бот, чужие не нужны.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user:
            if event.from_user.id != settings.telegram_user_id:
                await event.answer("⛔ Этот бот приватный.")
                return None
        return await handler(event, data)
