from __future__ import annotations

from datetime import datetime, timezone

import httpx
from pydantic import BaseModel

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
_RAIN_MAINS = {"Rain", "Drizzle", "Thunderstorm"}


class WeatherData(BaseModel):
    temp: float
    feels_like: float
    description: str
    wind_speed: float


class WeatherClient(BaseIntegration):
    """Получает текущую погоду через OpenWeatherMap API."""

    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self._http = http_client

    async def get_current_weather(self, city: str = settings.openweather_city) -> WeatherData:
        response = await self._http.get(
            BASE_URL,
            params={
                "q": city,
                "appid": settings.openweather_api_key,
                "units": "metric",
                "lang": "ru",
            },
        )
        response.raise_for_status()
        data = response.json()

        return WeatherData(
            temp=round(data["main"]["temp"]),
            feels_like=round(data["main"]["feels_like"]),
            description=data["weather"][0]["description"],
            wind_speed=data["wind"]["speed"],
        )

    async def get_forecast_rain(
        self,
        start: datetime,
        end: datetime,
        city: str = settings.openweather_city,
    ) -> bool:
        """Проверяет, ожидается ли дождь в интервале [start, end].

        Использует OpenWeather 5 day / 3 hour forecast. Слот считается «дождевым»,
        если его `weather[].main` ∈ Rain/Drizzle/Thunderstorm или объём осадков > 0.
        Слоты, не пересекающиеся с интервалом, игнорируются.
        """
        if start.tzinfo is None or end.tzinfo is None:
            raise ValueError("start/end must be timezone-aware")
        start_utc = start.astimezone(timezone.utc)
        end_utc = end.astimezone(timezone.utc)

        response = await self._http.get(
            FORECAST_URL,
            params={
                "q": city,
                "appid": settings.openweather_api_key,
                "units": "metric",
                "lang": "ru",
            },
        )
        response.raise_for_status()
        data = response.json()

        for item in data.get("list", []):
            # Каждый слот — окно [dt, dt + 3h)
            slot_start = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
            slot_end = datetime.fromtimestamp(item["dt"] + 3 * 3600, tz=timezone.utc)
            if slot_end <= start_utc or slot_start >= end_utc:
                continue
            mains = {w.get("main") for w in item.get("weather", [])}
            if mains & _RAIN_MAINS:
                return True
            rain_mm = (item.get("rain") or {}).get("3h", 0)
            snow_mm = (item.get("snow") or {}).get("3h", 0)
            if rain_mm > 0 or snow_mm > 0:
                return True
        return False
