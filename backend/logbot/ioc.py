# ruff: noqa: PLR6301
from __future__ import annotations

import ssl
from collections.abc import AsyncIterator
from typing import Annotated, Literal

import certifi
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage, SimpleEventIsolation
from aiogram.types import LinkPreviewOptions
from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, TCPConnector
from aiohttp_socks import ProxyConnector
from dishka import FromComponent, Provider, Scope, provide

from backend.bot.tg_http import RetryAiohttpSession
from backend.core.config import settings

type HttpSsl = ssl.SSLContext | Literal[False]


class MainProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_session(
        self, ssl: Annotated[HttpSsl, FromComponent("ssl")]
    ) -> AsyncIterator[ClientSession]:
        if settings.telegram_use_proxy and settings.telegram_socks_proxy:
            connector = ProxyConnector.from_url(settings.telegram_socks_proxy, ssl=ssl)
        else:
            connector = TCPConnector(ssl=ssl)
        async with ClientSession(
            connector=connector,
            cookie_jar=DummyCookieJar(),
            timeout=ClientTimeout(total=20, connect=5),
        ) as s:
            yield s


class AiogramProvider(Provider):
    scope = Scope.APP
    component = "aiogram"

    @provide(cache=False)
    def bot(
        self, http_session: Annotated[ClientSession, FromComponent()]
    ) -> Bot:
        return Bot(
            settings.telegram_logbot_token,
            session=RetryAiohttpSession(http_session),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                allow_sending_without_reply=True,
                link_preview=LinkPreviewOptions(is_disabled=True),
            ),
        )

    @provide(cache=False)
    def dispatcher(self) -> Dispatcher:
        return Dispatcher(
            storage=MemoryStorage(),
            events_isolation=SimpleEventIsolation(),
        )


class SslProvider(Provider):
    scope = Scope.APP
    component = "ssl"

    @provide
    async def cafile(self) -> str:
        import asyncio
        return await asyncio.to_thread(certifi.where)

    @provide(cache=False)
    async def http_ssl(self) -> HttpSsl:
        return False
