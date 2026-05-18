from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest

from backend.core.config import settings
from backend.core.logging import LOG_DIR

logger = logging.getLogger(__name__)

SERVICES = ("api", "bot", "scheduler", "logbot")
MAX_TG_TEXT = 3500


def _err_path(service: str) -> Path:
    return LOG_DIR / f"{service}.error.log"


class _FilePos:
    """Tracks current read offset and inode for log rotation detection."""

    def __init__(self) -> None:
        self.inode: int | None = None
        self.offset: int = 0

    def initialize(self, path: Path) -> None:
        """Seek to end on startup — we don't want to spam historical errors."""
        if not path.exists():
            self.inode = None
            self.offset = 0
            return
        stat = path.stat()
        self.inode = stat.st_ino
        self.offset = stat.st_size

    def read_new(self, path: Path) -> str:
        if not path.exists():
            self.inode = None
            self.offset = 0
            return ""
        stat = path.stat()
        if self.inode != stat.st_ino or stat.st_size < self.offset:
            self.inode = stat.st_ino
            self.offset = 0
        if stat.st_size == self.offset:
            return ""
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(self.offset)
            chunk = f.read()
            self.offset = f.tell()
        return chunk


async def run_error_tailer(bot: Bot) -> None:
    """Background task: push new ERROR/CRITICAL lines from *.error.log to owner."""
    chat_id = settings.telegram_logbot_chat_id or settings.telegram_user_id
    if not chat_id:
        logger.warning("No chat_id configured for log push; tailer disabled")
        return

    positions: dict[str, _FilePos] = {svc: _FilePos() for svc in SERVICES}
    for svc, pos in positions.items():
        pos.initialize(_err_path(svc))

    logger.info("Log tailer started, polling every %ss", settings.log_push_poll_seconds)
    while True:
        try:
            await asyncio.sleep(settings.log_push_poll_seconds)
            for svc, pos in positions.items():
                chunk = pos.read_new(_err_path(svc))
                if not chunk.strip():
                    continue
                await _send_chunked(bot, chat_id, svc, chunk)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Tailer iteration failed")


async def _send_chunked(bot: Bot, chat_id: int, service: str, text: str) -> None:
    header = f"❌ <b>{service}</b>\n"
    body = text.strip()
    # split into messages so each fits below Telegram's 4096 limit
    while body:
        piece = body[:MAX_TG_TEXT]
        body = body[MAX_TG_TEXT:]
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=f"{header}<pre>{_escape(piece)}</pre>",
            )
        except TelegramBadRequest:
            logger.exception("Failed to send error chunk for %s", service)


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
