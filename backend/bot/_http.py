from __future__ import annotations

import asyncio
import email.utils
import logging
from random import random
from time import time
from typing import TYPE_CHECKING, overload

from aiohttp import ClientConnectionError, ClientResponseError

from backend.bot.utils import maybe_create_exc_group

if TYPE_CHECKING:
    from collections.abc import Container, Mapping
    from typing import Unpack

    from aiohttp import ClientSession
    from aiohttp.client import _RequestOptions
    from aiohttp.typedefs import StrOrURL

DEFAULT_RETRY_ATTEMPTS = 3
_logger = logging.getLogger(__name__)


def _parse_retry_after_header(
    *, headers: Mapping[str, str] | None
) -> float | None:
    if headers is None:
        return None

    retry_header = headers.get("retry-after")
    if retry_header is None:
        return None

    try:
        return float(retry_header)
    except ValueError:
        pass

    retry_date_tuple = email.utils.parsedate_tz(retry_header)
    if retry_date_tuple is None:
        return None

    retry_date = email.utils.mktime_tz(retry_date_tuple)
    return float(retry_date - time())


@overload
def calculate_retry_timeout(
    *, headers: Mapping[str, str], attempt: int
) -> float | None: ...
@overload
def calculate_retry_timeout(*, headers: None, attempt: int) -> float: ...


def calculate_retry_timeout(
    *, headers: Mapping[str, str] | None, attempt: int
) -> float | None:
    retry_after = _parse_retry_after_header(headers=headers)
    if retry_after is not None:
        return (
            None
            if retry_after > 60  # noqa: PLR2004
            else max(0, retry_after)
        )
    sleep_seconds = 0.5 * (2**attempt)
    jitter = 1 - 0.25 * random()
    return max(0, sleep_seconds * jitter)


async def request(
    session: ClientSession,
    method: str,
    url: StrOrURL,
    /,
    *,
    retry_attempts: int = DEFAULT_RETRY_ATTEMPTS,
    retry_statuses: Container[int] = frozenset({408, 429, 500, 502, 503, 504}),
    **kwargs: Unpack[_RequestOptions],
) -> bytes:
    raise_for_status = kwargs.pop("raise_for_status", True)
    attempt = 0
    excs: list[Exception] = []
    try:
        while True:
            try:
                async with session.request(method, url, **kwargs) as response:
                    content = await response.read()
            except ClientConnectionError as e:
                excs.append(e)
                if attempt >= retry_attempts - 1:
                    break
                await asyncio.sleep(
                    calculate_retry_timeout(headers=None, attempt=attempt)
                )
                attempt += 1
                continue
            if raise_for_status:
                try:
                    response.raise_for_status()
                except ClientResponseError as e:
                    excs.append(e)
                    try:
                        response_text = content.decode(response.get_encoding())
                    except UnicodeDecodeError:
                        pass
                    else:
                        _logger.warning(
                            "%s %s %s %s",
                            response.method,
                            response.url,
                            response.status,
                            response_text,
                        )
                    if (
                        attempt >= retry_attempts - 1
                        or e.status not in retry_statuses
                    ):
                        break
                    timeout = calculate_retry_timeout(
                        headers=e.headers, attempt=attempt
                    )
                    if timeout is None:
                        break
                    await asyncio.sleep(timeout)
                    attempt += 1
                    continue
            if excs:
                _logger.error("", exc_info=maybe_create_exc_group(excs))
            return content
    except asyncio.CancelledError:
        if excs:
            _logger.exception("", exc_info=maybe_create_exc_group(excs))
        raise
    except Exception as e:
        excs.append(e)
    raise maybe_create_exc_group(excs)
