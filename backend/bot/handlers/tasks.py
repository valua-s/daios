from __future__ import annotations

import logging
from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dishka.integrations.aiogram import FromDishka, inject

from backend.bot.keyboards import (
    backlog_action_keyboard,
    task_action_keyboard,
    task_list_keyboard,
)
from backend.core.config import settings
from backend.models.task import TaskStatus
from backend.services.task_service import TaskService

logger = logging.getLogger(__name__)
router = Router(name="tasks")


class AddTaskState(StatesGroup):
    waiting_for_title = State()
    waiting_for_time = State()


def _add_time_keyboard() -> Any:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="task:skip_time")
    )
    return builder.as_markup()


def _after_add_keyboard() -> Any:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Добавить ещё", callback_data="task:add"),
        InlineKeyboardButton(text="📋 К списку задач", callback_data="task:back"),
    )
    return builder.as_markup()


# ── Команды ──────────────────────────────────────────────────────────────────

@router.message(Command("tasks"))
@inject
async def cmd_tasks(
    message: Message,
    task_service: FromDishka[TaskService],
) -> None:
    tasks = await task_service.get_today_tasks()

    if not tasks:
        await message.answer(
            "📋 На сегодня задач нет.",
            reply_markup=_after_add_keyboard(),
        )
        return

    await message.answer(
        f"📋 <b>Задачи на {datetime.now(ZoneInfo(settings.app_timezone)).date().strftime('%d.%m')}:</b>",
        reply_markup=task_list_keyboard(tasks),
    )


@router.message(Command("addtask"))
async def cmd_addtask(message: Message, state: FSMContext) -> None:
    await state.set_state(AddTaskState.waiting_for_title)
    await message.answer("✏️ Напиши текст задачи:")


@router.message(Command("backlog"))
@inject
async def cmd_backlog(
    message: Message,
    task_service: FromDishka[TaskService],
) -> None:
    items = await task_service.get_backlog()

    if not items:
        await message.answer("📥 Бэклог пуст.")
        return

    await message.answer(f"📥 <b>Бэклог ({len(items)} задач):</b>")
    for item in items:
        await message.answer(
            f"• {item.title}",
            reply_markup=backlog_action_keyboard(item.id),
        )


# ── FSM: добавление задачи ────────────────────────────────────────────────────

@router.callback_query(F.data == "task:add")
async def cb_task_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddTaskState.waiting_for_title)
    await callback.answer()
    await callback.message.answer("✏️ Напиши текст задачи:")


@router.message(AddTaskState.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext) -> None:
    if not message.text:
        await message.answer("Пожалуйста, отправь текст задачи.")
        return

    await state.update_data(title=message.text.strip())
    await state.set_state(AddTaskState.waiting_for_time)
    await message.answer(
        "⏰ В какое время? Напиши в формате <b>14:30</b> или пропусти:",
        reply_markup=_add_time_keyboard(),
    )


@router.callback_query(F.data == "task:skip_time", AddTaskState.waiting_for_time)
@inject
async def cb_skip_time(
    callback: CallbackQuery,
    state: FSMContext,
    task_service: FromDishka[TaskService],
) -> None:
    data = await state.get_data()
    task = await task_service.create_task(title=data["title"], source="telegram")
    await state.clear()
    await callback.answer()
    await callback.message.answer(
        f"✅ Задача добавлена: <b>{task.title}</b>",
        reply_markup=_after_add_keyboard(),
    )


@router.message(AddTaskState.waiting_for_time)
@inject
async def process_task_time(
    message: Message,
    state: FSMContext,
    task_service: FromDishka[TaskService],
) -> None:
    if not message.text:
        return

    scheduled_time: time | None = None
    try:
        parts = message.text.strip().split(":")
        scheduled_time = time(int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        await message.answer(
            "Не понял формат. Напиши как <b>14:30</b> или нажми Пропустить.",
            reply_markup=_add_time_keyboard(),
        )
        return

    data = await state.get_data()
    task = await task_service.create_task(
        title=data["title"],
        source="telegram",
        scheduled_time=scheduled_time,
    )
    await state.clear()

    time_str = scheduled_time.strftime("%H:%M")
    await message.answer(
        f"✅ Задача добавлена: <b>{task.title}</b> в {time_str}",
        reply_markup=_after_add_keyboard(),
    )


# ── Меню задачи ───────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("task:menu:"))
@inject
async def cb_task_menu(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    task = await task_service.get_task(task_id)

    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    status_icon = "✅" if task.status == TaskStatus.done else "⬜"
    time_str = f" · {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
    await callback.answer()
    await callback.message.edit_text(
        f"{status_icon} <b>{task.title}</b>{time_str}\n\nВыбери действие:",
        reply_markup=task_action_keyboard(task_id),
    )


@router.callback_query(F.data == "task:back")
@inject
async def cb_task_back(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    tasks = await task_service.get_today_tasks()
    await callback.answer()
    if tasks:
        await callback.message.edit_text(
            f"📋 <b>Задачи на {datetime.now(ZoneInfo(settings.app_timezone)).date().strftime('%d.%m')}:</b>",
            reply_markup=task_list_keyboard(tasks),
        )
    else:
        await callback.message.edit_text(
            "📋 На сегодня задач нет.",
            reply_markup=_after_add_keyboard(),
        )


@router.callback_query(F.data.startswith("task:toggle:"))
@inject
async def cb_task_toggle(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    task = await task_service.toggle_task(task_id)

    if not task:
        await callback.answer("Задача не найдена", show_alert=True)
        return

    icon = "✅" if task.status == TaskStatus.done else "⬜"
    time_str = f" · {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
    await callback.answer(f"{icon} {task.title}")
    await callback.message.edit_text(
        f"{icon} <b>{task.title}</b>{time_str}\n\nВыбери действие:",
        reply_markup=task_action_keyboard(task_id),
    )


@router.callback_query(F.data.startswith("task:delete:"))
@inject
async def cb_task_delete(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    await task_service.delete_task(task_id)
    await callback.answer("🗑 Удалено")

    tasks = await task_service.get_today_tasks()
    if tasks:
        await callback.message.edit_text(
            f"📋 <b>Задачи на {datetime.now(ZoneInfo(settings.app_timezone)).date().strftime('%d.%m')}:</b>",
            reply_markup=task_list_keyboard(tasks),
        )
    else:
        await callback.message.edit_text(
            "📋 На сегодня задач нет.",
            reply_markup=_after_add_keyboard(),
        )


# ── Бэклог ────────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("backlog:postpone:"))
@inject
async def cb_backlog_postpone(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    item_id = int(callback.data.split(":")[-1])
    await task_service.move_from_backlog_to_today(item_id)
    await callback.answer("📅 Перенесено на сегодня")
    await callback.message.delete()


@router.callback_query(F.data.startswith("backlog:move:"))
@inject
async def cb_backlog_move(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    await task_service.move_to_backlog(task_id)
    await callback.answer("🗂 Отправлено в бэклог")

    tasks = await task_service.get_today_tasks()
    if tasks:
        await callback.message.edit_text(
            f"📋 <b>Задачи на {datetime.now(ZoneInfo(settings.app_timezone)).date().strftime('%d.%m')}:</b>",
            reply_markup=task_list_keyboard(tasks),
        )
    else:
        await callback.message.edit_text(
            "📋 На сегодня задач нет.",
            reply_markup=_after_add_keyboard(),
        )


@router.callback_query(F.data.startswith("backlog:delete:"))
@inject
async def cb_backlog_delete(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    item_id = int(callback.data.split(":")[-1])
    await task_service.delete_backlog_item(item_id)
    await callback.answer("🗑 Удалено")
    await callback.message.delete()


# ── Вечерний итог ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("evening:postpone:"))
@inject
async def cb_evening_postpone(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    task = await task_service.postpone_task(task_id)
    if task:
        await callback.answer("📅 Перенесено на завтра")
    else:
        await callback.answer("Задача не найдена", show_alert=True)
    await callback.message.delete()


@router.callback_query(F.data == "evening:postpone_all")
@inject
async def cb_evening_postpone_all(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    count = await task_service.postpone_pending_to_tomorrow()
    await callback.answer(f"📅 Перенесено задач: {count}")
    await callback.message.edit_text(
        f"📅 {count} задач перенесено на завтра",
    )


@router.callback_query(F.data.startswith("evening:move:"))
@inject
async def cb_evening_move(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    await task_service.move_to_backlog(task_id)
    await callback.answer("🗂 Отправлено в бэклог")
    await callback.message.delete()


@router.callback_query(F.data.startswith("evening:delete:"))
@inject
async def cb_evening_delete(
    callback: CallbackQuery,
    task_service: FromDishka[TaskService],
) -> None:
    task_id = int(callback.data.split(":")[-1])
    await task_service.delete_task(task_id)
    await callback.answer("🗑 Удалено")
    await callback.message.delete()
