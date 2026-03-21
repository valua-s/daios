# ruff: noqa: PLR6301
from __future__ import annotations

import asyncio
import ssl
from collections.abc import AsyncIterator
from functools import partial
from typing import Annotated, Literal, override

import certifi
import valkey.asyncio as redis
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.memory import SimpleEventIsolation
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import LinkPreviewOptions
from aiohttp import ClientSession, ClientTimeout, DummyCookieJar, TCPConnector
from dishka import FromComponent, Provider, Scope, provide

from backend.core.config import settings
from backend.bot.tg_http import RetryAiohttpSession

type HttpSsl = ssl.SSLContext | Literal[False]
type RedisFactory = partial[redis.Redis]


class MainProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_session(
        self, ssl: Annotated[HttpSsl, FromComponent("ssl")]
    ) -> AsyncIterator[ClientSession]:
        async with ClientSession(
            connector=TCPConnector(ssl=ssl),
            cookie_jar=DummyCookieJar(),
            timeout=ClientTimeout(total=60, connect=5),
        ) as s:
            yield s

    @provide
    async def redis_factory(self) -> AsyncIterator[RedisFactory]:
        pool = redis.ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
        )
        try:
            yield partial(redis.Redis, connection_pool=pool)
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
                allow_sending_without_reply=True,
                link_preview=LinkPreviewOptions(is_disabled=True),
            ),
        )

    @provide(cache=False)
    def dispatcher(self, redis: redis.Redis) -> Dispatcher:
        return Dispatcher(
            storage=RedisStorage(
                redis,  # type: ignore[arg-type]
                key_builder=DefaultKeyBuilder(with_destiny=True),
                state_ttl=604000,
                data_ttl=604000,
            ),
            events_isolation=SimpleEventIsolation(),
        )

    @provide(cache=False)
    async def redis(self) -> AsyncIterator[redis.Redis]:
        async with redis.Redis(
            host=settings.redis_host, port=settings.redis_port,
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
