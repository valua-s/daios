from __future__ import annotations

from collections import deque
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, Message

from backend.core.logging import LOG_DIR
from backend.logbot.services.tailer import MAX_TG_TEXT, SERVICES

router = Router(name="logs")

DEFAULT_TAIL = 50
MAX_TAIL = 1000


def _tail(path: Path, n: int) -> str:
    if not path.exists():
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return "".join(deque(f, maxlen=n))


def _parse_args(args: str | None) -> tuple[str | None, int]:
    service: str | None = None
    n = DEFAULT_TAIL
    for tok in (args or "").split():
        if tok.isdigit():
            n = min(int(tok), MAX_TAIL)
        elif tok in SERVICES:
            service = tok
    return service, n


def _escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


async def _reply(message: Message, service: str, content: str) -> None:
    if not content.strip():
        await message.answer(f"<i>{service}: пусто</i>")
        return
    if len(content) <= MAX_TG_TEXT:
        await message.answer(f"<b>{service}</b>\n<pre>{_escape(content)}</pre>")
        return
    file = BufferedInputFile(content.encode("utf-8"), filename=f"{service}.log.txt")
    await message.answer_document(file, caption=f"<b>{service}</b>")


@router.message(Command("tail"))
async def cmd_tail(message: Message, command: CommandObject) -> None:
    """/tail [service] [N] — последние N строк из <service>.log (default: bot, 50)."""
    service, n = _parse_args(command.args)
    service = service or "bot"
    content = _tail(LOG_DIR / f"{service}.log", n)
    await _reply(message, f"{service}.log (last {n})", content)


@router.message(Command("logs"))
async def cmd_logs(message: Message, command: CommandObject) -> None:
    """/logs <service> [N] — alias of /tail with explicit service."""
    service, n = _parse_args(command.args)
    if service is None:
        await message.answer(
            f"Использование: /logs &lt;service&gt; [N]\nservice ∈ {{{', '.join(SERVICES)}}}"
        )
        return
    content = _tail(LOG_DIR / f"{service}.log", n)
    await _reply(message, f"{service}.log (last {n})", content)


@router.message(Command("errors"))
async def cmd_errors(message: Message, command: CommandObject) -> None:
    """/errors [service] [N] — последние N строк из *.error.log (по умолчанию — всех сервисов)."""
    service, n = _parse_args(command.args)
    targets = [service] if service else list(SERVICES)
    parts: list[str] = []
    for svc in targets:
        chunk = _tail(LOG_DIR / f"{svc}.error.log", n)
        if chunk.strip():
            parts.append(f"=== {svc} ===\n{chunk}")
    content = "\n".join(parts)
    await _reply(message, f"errors (last {n})", content)


@router.message(Command("start", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "<b>DAIOS log bot</b>\n"
        "/tail [service] [N] — хвост обычного лога\n"
        "/logs &lt;service&gt; [N] — то же, требует service\n"
        "/errors [service] [N] — хвост error-лога\n"
        f"\nservices: {', '.join(SERVICES)}"
    )
