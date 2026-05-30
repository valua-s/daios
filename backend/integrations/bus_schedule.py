from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

_MIN_CELLS_REQUIRED = 3
_COMMENT_CELL_INDEX = 4


class BusArrival(BaseModel):
    route: str
    departure_time: time
    bus_numbers: str
    comment: str = ""
    minutes_until: int = 0


class BusScheduleParser(BaseIntegration):
    """Парсит расписание автобусов с http://3aic.ru/.

    Ищет рейсы по маршруту: содержит оба слова из фильтра.
    """

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_next_departures(
        self,
        url: str,
        route_includes: tuple[str, ...] = ("Южный", "Курчатов"),
        count: int = 3,
    ) -> list[BusArrival]:
        """Возвращает `count` ближайших рейсов по маршруту."""
        response = await self._http.get(url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.find_all("tr")
        now = datetime.now(ZoneInfo(settings.app_timezone)).time()
        arrivals: list[BusArrival] = []

        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) < _MIN_CELLS_REQUIRED:
                continue

            time_str = cells[0]
            route = cells[1]
            bus_numbers = cells[2]
            comment = cells[_COMMENT_CELL_INDEX] if len(cells) > _COMMENT_CELL_INDEX else ""

            if not all(word.lower() in route.lower() for word in route_includes):
                continue

            try:
                parsed_time = datetime.strptime(time_str, "%H:%M").time()  # noqa: DTZ007
            except ValueError:
                continue

            # Считаем минут до отправления
            now_minutes = now.hour * 60 + now.minute
            dep_minutes = parsed_time.hour * 60 + parsed_time.minute
            minutes_until = dep_minutes - now_minutes

            # Пропускаем уже ушедшие
            if minutes_until < 0:
                continue

            arrivals.append(BusArrival(
                route=route,
                departure_time=parsed_time,
                bus_numbers=bus_numbers,
                comment=comment,
                minutes_until=minutes_until,
            ))

        arrivals.sort(key=lambda a: a.departure_time)
        return arrivals[:count]
