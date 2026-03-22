from __future__ import annotations

import httpx
from pydantic import BaseModel

from backend.core.config import settings
from backend.integrations.base import BaseIntegration

BASE_URL = "https://api.openweathermap.org/data/2.5/weather"


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
