from __future__ import annotations

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get, put

from backend.api.schemas import FocusDTO, SetFocusRequest
from backend.models.focus import Focus
from backend.services.focus_service import FocusService


def _to_dto(focus: Focus) -> FocusDTO:
    return FocusDTO(
        id=focus.id,
        period=focus.period.value,
        period_key=focus.period_key,
        description=focus.description,
        is_active=focus.is_active,
    )


class FocusController(Controller):
    path = "/api/focus"

    @get("/")
    async def get_focus(self, focus_service: FromDishka[FocusService]) -> dict[str, FocusDTO | None]:  # noqa: PLR6301
        week = await focus_service.get_current_week_focus()
        month = await focus_service.get_current_month_focus()
        return {
            "week": _to_dto(week) if week else None,
            "month": _to_dto(month) if month else None,
        }

    @put("/week")
    async def set_week_focus(  # noqa: PLR6301
        self,
        data: SetFocusRequest,
        focus_service: FromDishka[FocusService],
    ) -> FocusDTO:
        focus = await focus_service.set_week_focus(data.description)
        return _to_dto(focus)

    @put("/month")
    async def set_month_focus(  # noqa: PLR6301
        self,
        data: SetFocusRequest,
        focus_service: FromDishka[FocusService],
    ) -> FocusDTO:
        focus = await focus_service.set_month_focus(data.description)
        return _to_dto(focus)
