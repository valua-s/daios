from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from backend.core.config import settings

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from typing import Any


def allowed_chat_id() -> int:
    return settings.telegram_logbot_chat_id or settings.telegram_user_id


class OwnerOnlyMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        allowed = allowed_chat_id()
        user = getattr(event, "from_user", None)
        if user and user.id != allowed:
            if isinstance(event, Message):
                await event.answer("⛔ Этот бот приватный.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Этот бот приватный.", show_alert=True)
            return None
        return await handler(event, data)
