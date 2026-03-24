from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, TCPConnector
from aiohttp_socks import ProxyConnector

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

if TYPE_CHECKING:
    import ssl

    from aiogram.types import InlineKeyboardMarkup


def _make_bot() -> Bot:
    """Создаёт Bot с SOCKS5-прокси и без SSL-верификации (если настроено)."""
    ssl_ctx: ssl.SSLContext | bool = False  # NoSSL — как в боте

    if settings.telegram_use_proxy and settings.telegram_socks_proxy:
        connector = ProxyConnector.from_url(settings.telegram_socks_proxy, ssl=ssl_ctx)
    else:
        connector = TCPConnector(ssl=ssl_ctx)

    aiohttp_session = ClientSession(
        connector=connector,
        cookie_jar=DummyCookieJar(),
        timeout=ClientTimeout(total=20, connect=5),
    )

    class _OwnedSession(AiohttpSession):
        """AiohttpSession, владеющая уже созданной ClientSession."""

        def __init__(self) -> None:
            super().__init__()
            self._session = aiohttp_session

        async def create_session(self) -> ClientSession:  # type: ignore[override]
            return self._session

        async def close(self) -> None:
            await self._session.close()

    return Bot(
        token=settings.telegram_bot_token,
        session=_OwnedSession(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


class TelegramNotifier(BaseIntegration):
    """Отправляет сообщения владельцу бота.
    Используется агентами и планировщиком — не хендлерами.
    Хендлеры работают с Bot напрямую через aiogram.
    """

    def __init__(self) -> None:
        self._bot = _make_bot()
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
