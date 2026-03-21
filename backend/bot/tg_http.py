from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, override

from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import (
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods import GetUpdates

from backend.bot._http import DEFAULT_RETRY_ATTEMPTS, calculate_retry_timeout
from backend.bot.utils import maybe_create_exc_group

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.methods import TelegramMethod
    from aiogram.methods.base import TelegramType
    from aiohttp import ClientSession

_logger = logging.getLogger(__name__)


class RetryAiohttpSession(AiohttpSession):
    def __init__(self, session: ClientSession, /) -> None:
        super().__init__()
        self._session = session

    @override
    async def create_session(self) -> ClientSession:
        if self._session is None:
            raise RuntimeError
        return self._session

    @override
    async def close(self) -> None:
        pass

    @override
    async def make_request(
        self,
        bot: Bot,
        method: TelegramMethod[TelegramType],
        timeout: int | None = None,
    ) -> TelegramType:
        if isinstance(method, GetUpdates):
            return await super().make_request(bot, method, timeout)
        attempt = 0
        excs: list[Exception] = []
        try:
            while True:
                try:
                    r = await super().make_request(bot, method, timeout)
                except TelegramRetryAfter as e:
                    excs.append(e)
                    await asyncio.sleep(max(0, e.retry_after))
                except (TelegramNetworkError, TelegramServerError) as e:
                    excs.append(e)
                    if attempt >= DEFAULT_RETRY_ATTEMPTS - 1:
                        break
                    await asyncio.sleep(
                        calculate_retry_timeout(headers=None, attempt=attempt)
                    )
                    attempt += 1
                else:
                    if excs:
                        _logger.error("", exc_info=maybe_create_exc_group(excs))
                    return r
        except asyncio.CancelledError:
            if excs:
                _logger.exception("", exc_info=maybe_create_exc_group(excs))
            raise
        except Exception as e:
            excs.append(e)
        raise maybe_create_exc_group(excs)
