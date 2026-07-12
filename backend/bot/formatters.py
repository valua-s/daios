"""Форматирование текстов Telegram-сообщений.

Вынесено из handlers чтобы переиспользовать в scheduler.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from backend.integrations.bus_schedule import BusArrival
from backend.integrations.weather import WeatherData
from backend.models.content import ContentItem, ContentType
from backend.models.task import Task
from backend.services.wakeup_planner import WakeupPlan
from backend.services.workout_service import WorkoutPlan

if TYPE_CHECKING:
    from datetime import date


_DISCIPLINE_ICONS = {
    "running": "🏃",
    "cycling": "🚴",
    "swimming": "🏊",
    "strength": "💪",
}

_DISCIPLINE_LABELS = {
    "running": "Бег",
    "cycling": "Велосипед",
    "swimming": "Плавание",
    "strength": "Силовая",
}


def _segment_line(segment: dict) -> str:
    discipline = segment.get("discipline", "")
    icon = _DISCIPLINE_ICONS.get(discipline, "•")
    label = _DISCIPLINE_LABELS.get(discipline, "Тренировка")
    if segment.get("distance_km"):
        label = f"{label} {segment['distance_km']:g} км"
    elif segment.get("distance_m"):
        label = f"{label} {segment['distance_m']:g} м"
    elif segment.get("label"):
        label = f"{label} · {segment['label']}"
    minutes = segment.get("minutes")
    tail = f" · ~{minutes} мин" if minutes else ""
    return f"  {icon} {label}{tail}"


def format_workout(workout: WorkoutPlan | None) -> str:
    if workout is None or workout.type == "rest":
        desc = workout.description if workout else "День отдыха"
        return f"🛌 {desc}"

    segments = workout.details.get("segments") or []
    if not segments:
        return f"💪 <b>Тренировка</b>\n{workout.description}"

    disciplines = list(dict.fromkeys(s["discipline"] for s in segments))
    icons = "".join(_DISCIPLINE_ICONS.get(d, "") for d in disciplines)
    title = " + ".join(_DISCIPLINE_LABELS.get(d, "Тренировка") for d in disciplines)
    lines = [
        f"{icons} <b>{title}</b>",
        f"⏱ ~{workout.duration_minutes} мин",
        *[_segment_line(s) for s in segments],
        f"📝 {workout.description}",
    ]
    return "\n".join(lines)


def format_content_items(items: list[ContentItem]) -> str:
    if not items:
        return ""
    lines = ["📖 <b>Почитать/посмотреть в дороге:</b>"]
    for item in items:
        icon = "▶️" if item.type == ContentType.video else "📄"
        duration = f" · {item.duration_minutes} мин" if item.duration_minutes else ""
        topic = f" [{item.topic}]" if item.topic else ""
        lines.append(f'  {icon} <a href="{item.url}">{item.title}</a>{duration}{topic}')
    return "\n".join(lines)


def format_morning_brief(
    today: date,
    tasks: list[Task],
    workout: WorkoutPlan | None,
    weather: WeatherData | None = None,
    bus_schedule: list[BusArrival] | None = None,
    content_items: list[ContentItem] | None = None,
    *,
    is_weekend: bool = False,
) -> str:
    lines = [f"🌅 <b>Доброе утро! {today.strftime('%d.%m.%Y')}</b>\n"]

    if weather:
        lines.append(
            f"🌤 {weather.temp}°C, ощущается как {weather.feels_like}°C, "
            f"{weather.description}, ветер {weather.wind_speed} м/с\n"
        )

    if not is_weekend:
        if bus_schedule:
            lines.append("🚌 <b>Ближайшие автобусы:</b>")
            for bus in bus_schedule:
                t = bus.departure_time.strftime("%H:%M")
                lines.append(f"  {t} (через {bus.minutes_until} мин) — №{bus.bus_numbers}")
            lines.append("")
    else:
        lines.append(format_workout(workout) + "\n")

    if tasks:
        lines.append(f"📋 <b>Задачи на сегодня ({len(tasks)}):</b>")
        for i, task in enumerate(tasks, 1):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task.priority.value, "⬜")
            lines.append(f"  {i}. {icon} {task.title}")
    else:
        lines.append("📋 Задач пока нет — добавь через /addtask")

    if content_items:
        lines.extend(["", format_content_items(content_items)])

    return "\n".join(lines)


def format_evening_brief(
    today: date,
    workout: WorkoutPlan | None,
    tasks: list[Task],
    bus_schedule: list[BusArrival] | None = None,
    content_items: list[ContentItem] | None = None,
    *,
    is_weekend: bool = False,
) -> str:
    lines = [f"🌇 <b>Добрый вечер! {today.strftime('%d.%m.%Y')}</b>\n"]

    if not is_weekend:
        if bus_schedule:
            lines.append("🚌 <b>Ближайшие автобусы:</b>")
            for bus in bus_schedule:
                t = bus.departure_time.strftime("%H:%M")
                lines.append(f"  {t} (через {bus.minutes_until} мин) — №{bus.bus_numbers}")
            lines.append("")
        lines.append(format_workout(workout) + "\n")

    if tasks:
        lines.append(f"📋 <b>Задачи на сегодня ({len(tasks)}):</b>")
        for i, task in enumerate(tasks, 1):
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(task.priority.value, "⬜")
            lines.append(f"  {i}. {icon} {task.title}")
    else:
        lines.append("📋 Задач пока нет — добавь через /addtask")

    if content_items:
        lines.extend(["", format_content_items(content_items)])

    return "\n".join(lines)


def _workout_icon(workout: WorkoutPlan) -> str:
    disciplines = workout.details.get("disciplines") or [workout.type]
    icons = "".join(_DISCIPLINE_ICONS.get(d, "") for d in disciplines)
    return icons or "💪"


def format_wakeup_plan(plan: WakeupPlan) -> str:
    icon = _workout_icon(plan.workout)
    when_ru = "утром" if plan.when == "morning" else "вечером"
    alarm = plan.alarm_time.strftime("%H:%M")
    rain_note = ""
    if plan.when == "evening" and plan.rain_expected:
        rain_note = " (утром обещают дождь)"
    return (
        f"⏰ <b>Завтра:</b> {icon} {plan.workout.description} — {when_ru}{rain_note}\n"
        f"   Подъём в <b>{alarm}</b>"
    )


def format_evening_summary(done: list[Task], pending: list[Task]) -> str:
    total = len(done) + len(pending)
    lines = ["🌙 <b>Итоги дня</b>\n"]

    if total == 0:
        lines.append("📋 Сегодня задач не было.")
        return "\n".join(lines)

    lines.append(f"✅ Выполнено: {len(done)}/{total}\n")

    if done:
        lines.append("<b>Сделано:</b>")
        lines.extend(f"  ✅ {task.title}" for task in done)
        lines.append("")

    if pending:
        lines.append(f"<b>Не выполнено ({len(pending)}):</b>")
        for task in pending:
            time_str = f" · {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
            lines.append(f"  ⏳ {task.title}{time_str}")
        lines.extend(("", "Невыполненные задачи будут перенесены в бэклог в полночь.\nМожешь перенести на завтра, отправить в бэклог или удалить:"))

    return "\n".join(lines)
