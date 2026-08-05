from __future__ import annotations

import asyncio
import logging
import re
import time
from typing import TYPE_CHECKING

import gspread
from google.oauth2.service_account import Credentials

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import date

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

ROWS_CACHE_TTL_SECONDS = 120
RATE_LIMIT_STATUS = 429
RETRY_ATTEMPTS = 4
RETRY_BASE_DELAY_SECONDS = 2.0

# Порядок дней в таблице (столбцы 1-7 после колонки "Неделя")
WEEKDAY_COLUMNS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]

# Диапазон темпа бега в минутах на км
PACE_MIN = 6.0
PACE_MAX = 6.5
PACE_AVG = (PACE_MIN + PACE_MAX) / 2  # 6:15 — среднее

# Длительность силовой части в минутах, когда явно не указана
STRENGTH_MIN = 20
STRENGTH_MAX = 30
STRENGTH_AVG = (STRENGTH_MIN + STRENGTH_MAX) / 2  # 25 мин

# Средний темп велосипеда и плавания для оценки длительности
CYCLING_MIN_PER_KM = 2.5      # ~24 км/ч
SWIM_MIN_PER_100M = 2.0       # ~2 мин на 100 м

RUNNING = "running"
CYCLING = "cycling"
SWIMMING = "swimming"
STRENGTH = "strength"
COMBINED = "combined"
REST = "rest"

_DISCIPLINE_EMOJI = {"🏊": SWIMMING, "🚴": CYCLING, "🏃": RUNNING}
_STRENGTH_WORDS = ("силов", "верх", "низ", "корпус")
_REST_WORDS = ("отдых", "rest")


class GoogleSheetsClient(BaseIntegration):
    """Читает расписание тренировок из Google Sheets.

    Лист "BY GPT": строки — недели (1-16), столбцы — дни недели.
    Первый столбец — номер недели в году.
    """

    def __init__(self) -> None:
        creds = Credentials.from_service_account_file(
            settings.google_credentials_file,
            scopes=SCOPES,
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet_id = settings.google_sheets_workout_id
        self._worksheet_name = settings.google_sheets_worksheet
        self._worksheet: gspread.Worksheet | None = None
        self._rows_cache: list[dict] | None = None
        self._rows_cached_at = 0.0
        self._lock = asyncio.Lock()

    async def get_workout_for_date(self, target_date: date) -> dict | None:
        """Возвращает сырые данные тренировки для конкретной даты.

        Ищет нужную неделю по номеру ISO-недели года, затем берёт нужный день.
        """
        rows = await self._get_rows()
        return self._pick_day(rows, target_date)

    async def get_workouts_for_dates(self, dates: Iterable[date]) -> dict[date, dict | None]:
        """Читает таблицу один раз и раскладывает тренировки по датам."""
        rows = await self._get_rows()
        return {d: self._pick_day(rows, d) for d in dates}

    def invalidate_cache(self) -> None:
        self._rows_cache = None
        self._rows_cached_at = 0.0

    @staticmethod
    def _pick_day(rows: list[dict], target_date: date) -> dict | None:
        week_number = target_date.isocalendar().week
        weekday_index = target_date.weekday()  # 0=ПН, 6=ВС

        for row in rows:
            # Первый столбец — номер недели, может быть int или str
            try:
                row_week = int(row.get("Неделя", -1))
            except (ValueError, TypeError):
                continue

            if row_week == week_number:
                day_col = WEEKDAY_COLUMNS[weekday_index]
                raw_text = row.get(day_col, "").strip()
                return {"raw": raw_text, "week": row_week, "day": day_col}

        return None

    async def _get_rows(self) -> list[dict]:
        async with self._lock:
            if (
                self._rows_cache is not None
                and time.monotonic() - self._rows_cached_at < ROWS_CACHE_TTL_SECONDS
            ):
                return self._rows_cache

            rows = await self._fetch_all_rows_with_retry()
            self._rows_cache = rows
            self._rows_cached_at = time.monotonic()
            return rows

    async def _fetch_all_rows_with_retry(self) -> list[dict]:
        delay = RETRY_BASE_DELAY_SECONDS
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                return await asyncio.to_thread(self._fetch_all_rows)
            except gspread.exceptions.APIError as exc:
                if exc.response.status_code != RATE_LIMIT_STATUS or attempt == RETRY_ATTEMPTS:
                    raise
                self._worksheet = None
                logger.warning(
                    "Google Sheets quota exceeded, retry %d/%d in %.0fs",
                    attempt, RETRY_ATTEMPTS - 1, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
        return []

    def _fetch_all_rows(self) -> list[dict]:
        """Синхронное чтение всех строк таблицы."""
        all_values = self._get_worksheet().get_all_values()
        if not all_values:
            return []

        # Ищем строку-заголовок — ту где есть "Неделя"
        header_idx = None
        for i, row in enumerate(all_values):
            if "Неделя" in row:
                header_idx = i
                break

        if header_idx is None:
            return []

        headers = all_values[header_idx]
        rows = []
        for row in all_values[header_idx + 1:]:
            # Пропускаем пустые строки
            if not any(cell.strip() for cell in row):
                continue
            padded = row + [""] * (len(headers) - len(row))
            rows.append({
                headers[i]: padded[i]
                for i in range(len(headers))
                if headers[i].strip()  # пропускаем пустые заголовки
            })
        return rows

    def _get_worksheet(self) -> gspread.Worksheet:
        if self._worksheet is None:
            spreadsheet = self._client.open_by_key(self._spreadsheet_id)
            self._worksheet = spreadsheet.worksheet(self._worksheet_name)
        return self._worksheet


def parse_workout_text(raw: str) -> dict:
    """Парсит текст ячейки в структурированный словарь.

    Одна ячейка может содержать несколько дисциплин через " + ":
    бег 🏃, велосипед 🚴, плавание 🏊 и силовая.

    Примеры входных строк:
      "Верх 50 мин + 🏊 1800 м"
      "Интервалы: 3 км + 6×800 + 2 км = 10 км"
      "🚴 работа 16 км + низ 30 мин"
      "10 км Z2"
      "🚴 работа 16 км + 🏊 2000 м"
      "🚴 2:00 + 🏃 15 мин"
      "🏃 18 км + корпус 15 мин"
    """
    if not raw:
        return _rest_plan()

    if _is_rest(raw):
        return _rest_plan(description=raw)

    segments = [_build_segment(text) for text in _split_segments(raw)]
    segments = [s for s in segments if s is not None]
    if not segments:
        return _rest_plan(description=raw)

    disciplines = list(dict.fromkeys(s["discipline"] for s in segments))
    run_km = sum(s["distance_km"] or 0.0 for s in segments if s["discipline"] == RUNNING)
    workout_type = disciplines[0] if len(disciplines) == 1 else COMBINED

    return {
        "type": workout_type,
        "description": raw,
        "duration_minutes": sum(s["minutes"] for s in segments),
        "details": {
            "segments": segments,
            "disciplines": disciplines,
            "total_km": round(run_km, 2),
            "run_km": round(run_km, 2),
            "pace_range": f"{PACE_MIN:.0f}:{int((PACE_MIN % 1) * 60):02d}–{PACE_MAX:.0f}:{int((PACE_MAX % 1) * 60):02d} мин/км",
        },
    }


def _split_segments(raw: str) -> list[str]:
    """Делит строку на сегменты по " + ", склеивая части без маркера дисциплины.

    "Интервалы: 3 км + 6×800 + 2 км = 10 км" — один беговой сегмент,
    "🚴 работа 16 км + низ 30 мин"           — велосипед и силовая.
    """
    groups: list[list[str]] = []
    for part in (p.strip() for p in re.split(r"\s\+\s", raw) if p.strip()):
        if _explicit_discipline(part) is None and groups:
            groups[-1].append(part)
        else:
            groups.append([part])
    return [" + ".join(g) for g in groups]


def _explicit_discipline(part: str) -> str | None:
    for emoji, discipline in _DISCIPLINE_EMOJI.items():
        if emoji in part:
            return discipline
    if any(word in part.lower() for word in _STRENGTH_WORDS):
        return STRENGTH
    return None


def _build_segment(text: str) -> dict | None:
    discipline = _explicit_discipline(text) or _default_discipline(text)
    if discipline is None:
        return None

    if discipline == SWIMMING:
        return _swim_segment(text)
    if discipline == CYCLING:
        return _cycling_segment(text)
    if discipline == STRENGTH:
        return _strength_segment(text)
    return _running_segment(text)


def _default_discipline(text: str) -> str | None:
    if _extract_km(text) or _extract_minutes(text):
        return RUNNING
    return None


def _running_segment(text: str) -> dict:
    km = _extract_km(text)
    minutes = round(km * PACE_AVG) if km else (_extract_minutes(text) or 0)
    return _segment(RUNNING, text, distance_km=km or None, minutes=minutes)


def _cycling_segment(text: str) -> dict:
    time_minutes = _extract_clock_minutes(text)
    km = _extract_km(text)
    minutes = time_minutes or (round(km * CYCLING_MIN_PER_KM) if km else 0)
    return _segment(CYCLING, text, distance_km=km or None, minutes=minutes)


def _swim_segment(text: str) -> dict:
    meters = _extract_meters(text)
    minutes = round(meters / 100 * SWIM_MIN_PER_100M) if meters else 0
    return _segment(SWIMMING, text, distance_m=meters or None, minutes=minutes)


def _strength_segment(text: str) -> dict:
    minutes = _extract_minutes(text) or int(STRENGTH_AVG)
    return _segment(STRENGTH, text, label=_strength_label(text), minutes=minutes)


def _segment(
    discipline: str,
    text: str,
    *,
    distance_km: float | None = None,
    distance_m: float | None = None,
    minutes: int = 0,
    label: str | None = None,
) -> dict:
    return {
        "discipline": discipline,
        "label": label,
        "distance_km": distance_km,
        "distance_m": distance_m,
        "minutes": minutes,
        "raw": text.strip(),
    }


def _strength_label(text: str) -> str:
    lowered = text.lower()
    for word in ("верх", "низ", "корпус"):
        if word in lowered:
            return word.capitalize()
    return "Силовая"


def _is_rest(raw: str) -> bool:
    text = raw.lower()
    if not any(w in text for w in _REST_WORDS):
        return False
    return _explicit_discipline(raw) is None and not _extract_km(text)


def _extract_km(text: str) -> float:
    """Суммирует упоминания километров, учитывая запись "…= 10 км" как итог.

    "3 км + 6×800 + 2 км = 10 км" → 10.0
    "16 км"                       → 16.0
    """
    matches = re.findall(r"(\d+[.,]?\d*)\s*км", text)
    if not matches:
        return 0.0
    values = [float(m.replace(",", ".")) for m in matches]
    if len(values) > 1 and values[-1] >= sum(values[:-1]):
        return values[-1]
    if len(values) > 1 and values[0] >= sum(values[1:]):
        return values[0]
    return sum(values)


def _extract_meters(text: str) -> float:
    matches = re.findall(r"(\d+[.,]?\d*)\s*м(?![а-яёa-z])", text.lower())
    return sum(float(m.replace(",", ".")) for m in matches)


def _extract_minutes(text: str) -> int:
    match = re.search(r"(\d+)\s*мин", text.lower())
    return int(match.group(1)) if match else 0


def _extract_clock_minutes(text: str) -> int:
    match = re.search(r"(\d+):(\d{2})", text)
    if not match:
        return 0
    return int(match.group(1)) * 60 + int(match.group(2))


def _rest_plan(description: str = "День отдыха") -> dict:
    return {
        "type": REST,
        "description": description,
        "duration_minutes": 0,
        "details": {"segments": [], "disciplines": []},
    }
