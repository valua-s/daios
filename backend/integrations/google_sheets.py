import asyncio
import re
from datetime import date

import gspread
from google.oauth2.service_account import Credentials

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
WORKSHEET_NAME = "BY GPT"

# Порядок дней в таблице (столбцы 1-7 после колонки "Неделя")
WEEKDAY_COLUMNS = ["ПН", "ВТ", "СР", "ЧТ", "ПТ", "СБ", "ВС"]

# Диапазон темпа бега в минутах на км
PACE_MIN = 6.0
PACE_MAX = 6.5
PACE_AVG = (PACE_MIN + PACE_MAX) / 2  # 6:15 — среднее

# Длительность силовой части в минутах
STRENGTH_MIN = 20
STRENGTH_MAX = 30
STRENGTH_AVG = (STRENGTH_MIN + STRENGTH_MAX) / 2  # 25 мин


class GoogleSheetsClient(BaseIntegration):
    """
    Читает расписание тренировок из Google Sheets.
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

    async def get_workout_for_date(self, target_date: date) -> dict | None:
        """
        Возвращает сырые данные тренировки для конкретной даты.
        Ищет нужную неделю по номеру ISO-недели года, затем берёт нужный день.
        """
        week_number = target_date.isocalendar().week
        weekday_index = target_date.weekday()  # 0=ПН, 6=ВС

        all_rows = await asyncio.to_thread(self._fetch_all_rows)

        for row in all_rows:
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

    def _fetch_all_rows(self) -> list[dict]:
        """Синхронное чтение всех строк таблицы."""
        spreadsheet = self._client.open_by_key(self._spreadsheet_id)
        worksheet = spreadsheet.worksheet(WORKSHEET_NAME)
        all_values = worksheet.get_all_values()
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


def parse_workout_text(raw: str) -> dict:
    """
    Парсит текст ячейки в структурированный словарь.

    Примеры входных строк:
      "Отдых + мобилити"
      "10 км Z2"
      "Силовая + легкий бег(5км)"
      "12 км: 8 км Z2 + 4×20″ (1:40 бег)"
      "8 км + силовая"
    """
    if not raw:
        return _rest_plan()

    text = raw.lower()

    is_rest = any(w in text for w in ["отдых", "rest"])
    has_running = bool(re.search(r"\d+[\.,]?\d*\s*км", text))
    has_strength = any(w in text for w in ["силовая", "strength"])

    if is_rest and not has_running and not has_strength:
        return _rest_plan(description=raw)

    total_km = _extract_total_km(text)
    run_minutes = int(total_km * PACE_AVG) if total_km else 0
    strength_minutes = STRENGTH_AVG if has_strength else 0
    total_minutes = run_minutes + int(strength_minutes)

    if has_running and has_strength:
        workout_type = "combined"
    elif has_running:
        workout_type = "running"
    elif has_strength:
        workout_type = "strength"
    else:
        return _rest_plan(description=raw)

    return {
        "type": workout_type,
        "description": raw,
        "duration_minutes": total_minutes,
        "details": {
            "total_km": total_km,
            "run_minutes": run_minutes,
            "strength_minutes": int(strength_minutes),
            "pace_range": f"{PACE_MIN:.0f}:{int((PACE_MIN % 1)*60):02d}–{PACE_MAX:.0f}:{int((PACE_MAX % 1)*60):02d} мин/км",
        },
    }


def _extract_total_km(text: str) -> float:
    """
    Суммирует все упоминания километров в строке.
    "8 км Z2 + 4×20″ (1:40 бег)" → 8.0
    "Силовая + легкий бег(5км)"   → 5.0
    "12 км: 8 км Z2 + ..."        → берём первое (общее) число
    """
    # Ищем все числа перед "км"
    matches = re.findall(r"(\d+[\.,]?\d*)\s*км", text)
    if not matches:
        return 0.0

    values = [float(m.replace(",", ".")) for m in matches]

    # Если первое число >= суммы остальных — это общая дистанция ("12 км: 8 км + ...")
    if len(values) > 1 and values[0] >= sum(values[1:]):
        return values[0]

    return sum(values)


def _rest_plan(description: str = "День отдыха") -> dict:
    return {
        "type": "rest",
        "description": description,
        "duration_minutes": 0,
        "details": {},
    }