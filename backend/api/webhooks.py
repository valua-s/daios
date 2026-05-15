from __future__ import annotations

import logging
from typing import Any

from dishka.integrations.litestar import FromDishka
from litestar import Controller, get, post
from litestar.exceptions import HTTPException
from litestar.params import Parameter

from backend.core.config import settings
from backend.services.strava_service import StravaService, StravaWebhookEvent

logger = logging.getLogger(__name__)


class StravaWebhookController(Controller):
    path = "/webhook"

    @get("/")
    async def verify(
        self,
        hub_mode: str = Parameter(query="hub.mode", default=""),
        hub_challenge: str = Parameter(query="hub.challenge", default=""),
        hub_verify_token: str = Parameter(query="hub.verify_token", default=""),
    ) -> dict[str, str]:
        """GET-валидация Strava-подписки."""
        if hub_mode != "subscribe" or hub_verify_token != settings.strava_webhook_verify_token:
            logger.warning("Strava webhook verify mismatch: mode=%s", hub_mode)
            raise HTTPException(status_code=403, detail="verify_token mismatch")
        return {"hub.challenge": hub_challenge}

    @post("/", status_code=200)
    async def receive(
        self,
        data: dict[str, Any],
        strava_service: FromDishka[StravaService],
    ) -> dict[str, str]:
        """POST от Strava. Обрабатываем синхронно — fetch + upsert обычно < 2s."""
        try:
            event = StravaWebhookEvent(
                object_type=str(data["object_type"]),
                object_id=int(data["object_id"]),
                aspect_type=str(data["aspect_type"]),
                owner_id=int(data["owner_id"]),
                event_time=int(data.get("event_time", 0)),
            )
        except (KeyError, ValueError, TypeError):
            logger.exception("Bad Strava webhook payload: %s", data)
            return {"status": "ignored"}

        try:
            await strava_service.handle_webhook_event(event)
        except Exception:
            logger.exception("Strava webhook handling failed for activity %s", event.object_id)

        return {"status": "ok"}
