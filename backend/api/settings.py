from __future__ import annotations

import re
from dataclasses import dataclass

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, patch, post
from litestar.exceptions import ClientException, NotFoundException

from backend.services.settings_service import ScheduleDTO, SettingsService

_VALID_KEY = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class ScheduleResponseDTO:
    event_name: str
    cron_expr: str
    enabled: bool
    description: str
    time: str
    cron_expr_weekend: str | None
    time_weekend: str | None
    supports_weekend: bool


@dataclass
class UpdateScheduleRequest:
    time: str
    enabled: bool
    time_weekend: str | None = None


@dataclass
class WakeupResponseDTO:
    base_time: str


@dataclass
class UpdateWakeupRequest:
    base_time: str


def _to_response(dto: ScheduleDTO) -> ScheduleResponseDTO:
    return ScheduleResponseDTO(
        event_name=dto.event_name,
        cron_expr=dto.cron_expr,
        enabled=dto.enabled,
        description=dto.description,
        time=dto.time,
        cron_expr_weekend=dto.cron_expr_weekend,
        time_weekend=dto.time_weekend,
        supports_weekend=dto.supports_weekend,
    )


class SettingsController(Controller):
    path = "/api/settings"

    @get("/interests")
    async def get_interests(  # noqa: PLR6301
        self, settings_service: FromDishka[SettingsService]
    ) -> dict[str, bool]:
        return await settings_service.get_interests()

    @post("/interests")
    async def set_interests(  # noqa: PLR6301
        self,
        data: dict[str, bool],
        settings_service: FromDishka[SettingsService],
    ) -> dict[str, bool]:
        await settings_service.set_interests(data)
        return await settings_service.get_interests()

    @post("/interests/{key:str}")
    async def add_interest(  # noqa: PLR6301
        self,
        key: str,
        settings_service: FromDishka[SettingsService],
    ) -> dict[str, bool]:
        if not _VALID_KEY.match(key):
            raise ClientException(detail="Invalid key format")
        await settings_service.add_interest(key)
        return await settings_service.get_interests()

    @delete("/interests/{key:str}", status_code=204)
    async def delete_interest(  # noqa: PLR6301
        self,
        key: str,
        settings_service: FromDishka[SettingsService],
    ) -> None:
        if not _VALID_KEY.match(key):
            raise ClientException(detail="Invalid key format")
        await settings_service.delete_interest(key)

    @get("/schedules")
    async def get_schedules(  # noqa: PLR6301
        self, settings_service: FromDishka[SettingsService]
    ) -> list[ScheduleResponseDTO]:
        schedules = await settings_service.get_schedules()
        return [_to_response(s) for s in schedules]

    @get("/wakeup")
    async def get_wakeup(  # noqa: PLR6301
        self, settings_service: FromDishka[SettingsService]
    ) -> WakeupResponseDTO:
        t = await settings_service.get_wakeup_base_time()
        return WakeupResponseDTO(base_time=t.strftime("%H:%M"))

    @patch("/wakeup")
    async def update_wakeup(  # noqa: PLR6301
        self,
        data: UpdateWakeupRequest,
        settings_service: FromDishka[SettingsService],
    ) -> WakeupResponseDTO:
        try:
            await settings_service.set_wakeup_base_time(data.base_time)
        except ValueError as e:
            raise ClientException(detail=str(e)) from e
        t = await settings_service.get_wakeup_base_time()
        return WakeupResponseDTO(base_time=t.strftime("%H:%M"))

    @patch("/schedules/{event_name:str}")
    async def update_schedule(  # noqa: PLR6301
        self,
        event_name: str,
        data: UpdateScheduleRequest,
        settings_service: FromDishka[SettingsService],
    ) -> ScheduleResponseDTO:
        try:
            result = await settings_service.update_schedule(
                event_name, data.time, enabled=data.enabled, time_weekend=data.time_weekend
            )
        except ValueError as e:
            raise ClientException(detail=str(e)) from e
        if result is None:
            raise NotFoundException(detail=f"Schedule '{event_name}' not found")
        return _to_response(result)
