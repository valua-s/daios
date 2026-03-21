from __future__ import annotations

from dataclasses import dataclass

from dishka.integrations.litestar import FromDishka
from litestar import Controller, delete, get, patch, post
from litestar.exceptions import NotFoundException

from backend.services.settings_service import ScheduleDTO, SettingsService


@dataclass
class ScheduleResponseDTO:
    event_name: str
    cron_expr: str
    enabled: bool
    description: str
    time: str


@dataclass
class UpdateScheduleRequest:
    time: str
    enabled: bool


def _to_response(dto: ScheduleDTO) -> ScheduleResponseDTO:
    return ScheduleResponseDTO(
        event_name=dto.event_name,
        cron_expr=dto.cron_expr,
        enabled=dto.enabled,
        description=dto.description,
        time=dto.time,
    )


class SettingsController(Controller):
    path = "/api/settings"

    @get("/interests")
    async def get_interests(
        self, settings_service: FromDishka[SettingsService]
    ) -> dict[str, bool]:
        return await settings_service.get_interests()

    @post("/interests")
    async def set_interests(
        self,
        data: dict[str, bool],
        settings_service: FromDishka[SettingsService],
    ) -> dict[str, bool]:
        await settings_service.set_interests(data)
        return await settings_service.get_interests()

    @post("/interests/{key:str}")
    async def add_interest(
        self,
        key: str,
        settings_service: FromDishka[SettingsService],
    ) -> dict[str, bool]:
        await settings_service.add_interest(key)
        return await settings_service.get_interests()

    @delete("/interests/{key:str}", status_code=204)
    async def delete_interest(
        self,
        key: str,
        settings_service: FromDishka[SettingsService],
    ) -> None:
        await settings_service.delete_interest(key)

    @get("/schedules")
    async def get_schedules(
        self, settings_service: FromDishka[SettingsService]
    ) -> list[ScheduleResponseDTO]:
        schedules = await settings_service.get_schedules()
        return [_to_response(s) for s in schedules]

    @patch("/schedules/{event_name:str}")
    async def update_schedule(
        self,
        event_name: str,
        data: UpdateScheduleRequest,
        settings_service: FromDishka[SettingsService],
    ) -> ScheduleResponseDTO:
        result = await settings_service.update_schedule(event_name, data.time, data.enabled)
        if result is None:
            raise NotFoundException(detail=f"Schedule '{event_name}' not found")
        return _to_response(result)
