from __future__ import annotations

import logging
from datetime import date

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka, inject

from backend.bot.formatters import format_workout
from backend.bot.keyboards import workout_keyboard
from backend.services.workout_service import WorkoutService

logger = logging.getLogger(__name__)
router = Router(name="workout")


@router.callback_query(F.data == "workout:done")
async def cb_workout_done(callback: CallbackQuery) -> None:
    await callback.message.answer("💪 Отлично, так держать!")
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]


@router.callback_query(F.data == "workout:skip")
async def cb_workout_skip(callback: CallbackQuery) -> None:
    await callback.message.answer("👌 Окей, бывает")
    await callback.message.edit_reply_markup(reply_markup=None)  # type: ignore[union-attr]


@router.message(Command("workout"))
@inject
async def cmd_workout(
    message: Message,
    workout_service: FromDishka[WorkoutService],
) -> None:
    await message.answer("⏳ Загружаю тренировку...")

    workout = await workout_service.get_workout_for_date(date.today())

    if workout is None or workout.type == "rest":
        await message.answer("😴 Сегодня день отдыха. Восстанавливайся!")
        return

    await message.answer(format_workout(workout), reply_markup=workout_keyboard())
