# ruff: noqa: PLR6301
from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator
from functools import partial
from typing import Annotated, Literal, override

import certifi
import valkey.asyncio as valkey
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import LinkPreviewOptions
from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, TCPConnector
from aiohttp_socks import ProxyConnector
from dishka import FromComponent, Provider, Scope, provide

from backend.bot.tg_http import RetryAiohttpSession
from backend.core.config import settings

type HttpSsl = ssl.SSLContext | Literal[False]
type RedisFactory = partial[valkey.Redis]


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

    @provide
    async def redis_factory(self) -> AsyncIterator[RedisFactory]:
        pool = valkey.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
        )
        try:
            yield partial(valkey.Redis, connection_pool=pool)
        finally:
            await pool.aclose()


class AiogramProvider(Provider):
    scope = Scope.APP
    component = "aiogram"

    @provide(cache=False)
    def bot(
        self, http_session: Annotated[ClientSession, FromComponent()]
    ) -> Bot:
        return Bot(
            settings.telegram_bot_token,
            session=RetryAiohttpSession(http_session),
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                allow_sending_without_reply=True,
                link_preview=LinkPreviewOptions(is_disabled=True),
            ),
        )

    @provide(cache=False)
    def dispatcher(self, redis_client: valkey.Redis) -> Dispatcher:
        return Dispatcher(
            storage=RedisStorage(
                redis_client,  # type: ignore[arg-type]
                key_builder=DefaultKeyBuilder(with_destiny=True),
                state_ttl=604000,
                data_ttl=604000,
            ),
            events_isolation=SimpleEventIsolation(),
        )

    @provide(cache=False)
    async def redis_client(self) -> AsyncIterator[valkey.Redis]:
        async with valkey.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            username=settings.redis_user,
            password=settings.redis_password,
        ) as r:
            yield r


class SslProvider(Provider):
    scope = Scope.APP
    component = "ssl"

    @provide
    async def cafile(self) -> str:
        return await asyncio.to_thread(certifi.where)

    @provide(cache=False)
    async def http_ssl(self, cafile: str) -> HttpSsl:
        ssl_context = await asyncio.to_thread(
            ssl.create_default_context, cafile=cafile
        )
        # aiohttp supports only http/1.1
        ssl_context.set_alpn_protocols(("http/1.1",))
        return ssl_context


class NoSslProvider(SslProvider):
    @provide(cache=False)
    @override
    def http_ssl(self) -> HttpSsl:
        return False
