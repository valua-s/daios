import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dishka.integrations.aiogram import FromDishka, inject

from backend.services.focus_service import FocusService

logger = logging.getLogger(__name__)
router = Router(name="focus")


class SetFocusState(StatesGroup):
    choosing_period = State()
    waiting_for_description = State()


def _period_keyboard() -> any:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Неделя", callback_data="focus:period:week"),
        InlineKeyboardButton(text="🗓 Месяц", callback_data="focus:period:month"),
    )
    return builder.as_markup()


@router.message(Command("focus"))
@inject
async def cmd_focus(
    message: Message,
    focus_service: FromDishka[FocusService],
) -> None:
    week = await focus_service.get_current_week_focus()
    month = await focus_service.get_current_month_focus()

    lines = ["🎯 <b>Текущий фокус</b>\n"]

    if week:
        lines.append(f"📅 <b>Неделя:</b> {week.description}")
    else:
        lines.append("📅 <b>Неделя:</b> не задан")

    if month:
        lines.append(f"🗓 <b>Месяц:</b> {month.description}")
    else:
        lines.append("🗓 <b>Месяц:</b> не задан")

    lines.append("\nИзменить: /setfocus")
    await message.answer("\n".join(lines))


@router.message(Command("setfocus"))
async def cmd_setfocus(message: Message, state: FSMContext) -> None:
    await state.set_state(SetFocusState.choosing_period)
    await message.answer(
        "🎯 Выбери период для фокуса:",
        reply_markup=_period_keyboard(),
    )


@router.callback_query(SetFocusState.choosing_period)
async def cb_focus_period(callback: CallbackQuery, state: FSMContext) -> None:
    period = callback.data.split(":")[-1]  # type: ignore[union-attr]
    await state.update_data(period=period)
    await state.set_state(SetFocusState.waiting_for_description)
    await callback.answer()
    await callback.message.delete()  # type: ignore[union-attr]

    period_label = "недели" if period == "week" else "месяца"
    await callback.message.answer(  # type: ignore[union-attr]
        f"✏️ Напиши фокус {period_label}.\n\n"
        "Например: <i>Углубиться в async Python и написать 3 pet-project задачи</i>"
    )


@router.message(SetFocusState.waiting_for_description)
@inject
async def process_focus_description(
    message: Message,
    state: FSMContext,
    focus_service: FromDishka[FocusService],
) -> None:
    if not message.text:
        await message.answer("Пожалуйста, отправь текст фокуса.")
        return

    data = await state.get_data()
    period = data["period"]
    description = message.text.strip()

    if period == "week":
        await focus_service.set_week_focus(description)
        label = "недели"
    else:
        await focus_service.set_month_focus(description)
        label = "месяца"

    await state.clear()
    await message.answer(f"✅ Фокус {label} установлен:\n\n<i>{description}</i>")