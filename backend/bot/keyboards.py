from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.models.task import Task


def task_list_keyboard(tasks: list[Task]) -> InlineKeyboardMarkup:
    """Список задач — тап на задачу открывает меню действий."""
    builder = InlineKeyboardBuilder()
    for task in tasks:
        status_icon = "✅" if task.status == "done" else "⬜"
        time_str = f" {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
        builder.row(
            InlineKeyboardButton(
                text=f"{status_icon}{time_str} {task.title}",
                callback_data=f"task:menu:{task.id}",
            )
        )
    builder.row(
        InlineKeyboardButton(text="➕ Добавить задачу", callback_data="task:add")
    )
    return builder.as_markup()


def task_action_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Меню действий с конкретной задачей."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Выполнено", callback_data=f"task:toggle:{task_id}"),
        InlineKeyboardButton(text="🗂 В бэклог", callback_data=f"backlog:move:{task_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"task:delete:{task_id}"),
        InlineKeyboardButton(text="◀️ Назад", callback_data="task:back"),
    )
    return builder.as_markup()


def backlog_action_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Действия с незакрытой задачей вечером."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="📅 Перенести на завтра", callback_data=f"backlog:postpone:{task_id}"
        ),
        InlineKeyboardButton(
            text="🗂 В бэклог", callback_data=f"backlog:move:{task_id}"
        ),
        InlineKeyboardButton(
            text="🗑 Удалить", callback_data=f"backlog:delete:{task_id}"
        ),
    )
    return builder.as_markup()


def workout_keyboard() -> InlineKeyboardMarkup:
    """Кнопки под сообщением с тренировкой."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Готово", callback_data="workout:done"),
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="workout:skip"),
    )
    return builder.as_markup()


def confirm_keyboard(action: str, entity_id: int) -> InlineKeyboardMarkup:
    """Универсальная клавиатура подтверждения."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=f"{action}:confirm:{entity_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data=f"{action}:cancel:{entity_id}"),
    )
    return builder.as_markup()


def evening_task_keyboard(task_id: int) -> InlineKeyboardMarkup:
    """Кнопки под каждой невыполненной задачей в вечернем итоге."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🗂 В бэклог", callback_data=f"evening:move:{task_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"evening:delete:{task_id}"),
    )
    return builder.as_markup()
