from __future__ import annotations

import logging
import time

from litestar.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("backend.timing")


class TimingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_holder: dict[str, int] = {"status": 0}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        t0 = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            ms = round((time.perf_counter() - t0) * 1000)
            method = scope.get("method", "?")
            path = scope.get("path", "?")
            logger.info("HTTP %s %s -> %s in %s ms", method, path, status_holder["status"], ms)
