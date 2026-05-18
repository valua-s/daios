"""Форматирование текстов Telegram-сообщений.
Вынесено из handlers чтобы переиспользовать в scheduler.
"""
from __future__ import annotations

from datetime import date

from backend.integrations.bus_schedule import BusArrival
from backend.integrations.weather import WeatherData
from backend.models.content import ContentItem, ContentType
from backend.models.task import Task
from backend.services.wakeup_planner import WakeupPlan
from backend.services.workout_service import WorkoutPlan


def format_workout(workout: WorkoutPlan | None) -> str:
    if workout is None or workout.type == "rest":
        desc = workout.description if workout else "День отдыха"
        return f"🛌 {desc}"

    d = workout.details
    pace = d.get("pace_range", "6:00–6:30 мин/км")

    if workout.type == "running":
        km = d.get("total_km", "?")
        return (
            f"🏃 <b>Бег {km} км</b>\n"
            f"⏱ ~{workout.duration_minutes} мин · {pace}\n"
            f"📝 {workout.description}"
        )

    if workout.type == "strength":
        return (
            f"💪 <b>Силовая</b>\n"
            f"⏱ ~{workout.duration_minutes} мин\n"
            f"📝 {workout.description}"
        )

    if workout.type == "combined":
        km = d.get("total_km", "?")
        run_min = d.get("run_minutes", 0)
        str_min = d.get("strength_minutes", 0)
        return (
            f"🏋️🏃 <b>Силовая + бег {km} км</b>\n"
            f"⏱ ~{workout.duration_minutes} мин "
            f"(силовая {str_min} + бег {run_min})\n"
            f"📝 {workout.description}"
        )

    return f"💪 <b>Тренировка</b>\n{workout.description}"


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


_WORKOUT_ICONS = {
    "running": "🏃",
    "strength": "💪",
    "combined": "🏋️🏃",
}


def format_wakeup_plan(plan: WakeupPlan) -> str:
    icon = _WORKOUT_ICONS.get(plan.workout.type, "💪")
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
        for task in done:
            lines.append(f"  ✅ {task.title}")
        lines.append("")

    if pending:
        lines.append(f"<b>Не выполнено ({len(pending)}):</b>")
        for task in pending:
            time_str = f" · {task.scheduled_time.strftime('%H:%M')}" if task.scheduled_time else ""
            lines.append(f"  ⏳ {task.title}{time_str}")
        lines.append("")
        lines.append("Невыполненные задачи будут перенесены в бэклог в полночь.\nМожешь перенести на завтра, отправить в бэклог или удалить:")

    return "\n".join(lines)
