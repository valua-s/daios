import logging

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from dishka.integrations.aiogram import FromDishka, inject

from backend.agents.orchestrator import Orchestrator

logger = logging.getLogger(__name__)
router = Router(name="common")

HELP_TEXT = (
    "<b>DAIOS — твой AI-оператор дня</b>\n\n"
    "<b>📋 Задачи</b>\n"
    "/tasks — задачи на сегодня\n"
    "/addtask — добавить задачу\n"
    "/backlog — задачи без срока\n\n"
    "<b>🏋️ Тренировки</b>\n"
    "/workout — план тренировки на сегодня\n\n"
    "<b>🌅 Сводка</b>\n"
    "/morning — утренняя сводка прямо сейчас\n\n"
    "<b>⚙️ Прочее</b>\n"
    "/focus — текущий фокус недели и месяца\n"
    "/help — список команд"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "👋 Привет! Я <b>DAIOS</b> — твой персональный AI-оператор дня.\n\n"
        "Помогаю управлять задачами, слежу за тренировками и каждое утро "
        "собираю сводку: погода, автобусы, план на день.\n\n"
        + HELP_TEXT
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("morning"))
@inject
async def cmd_morning(
    message: Message,
    orchestrator: FromDishka[Orchestrator],
) -> None:
    await message.answer("⏳ Собираю сводку...")
    await orchestrator.run(state={})