from __future__ import annotations

import asyncio

import uvicorn
from dishka import make_async_container
from dishka.integrations.litestar import DishkaRouter, setup_dishka
from litestar import Litestar, get
from litestar.config.cors import CORSConfig

from backend.api.backlog import BacklogController
from backend.api.focus import FocusController
from backend.api.settings import SettingsController
from backend.api.tasks import TaskController
from backend.api.workouts import WorkoutController
from backend.core.config import settings
from backend.core.minio_client import ensure_bucket
from backend.core.providers import AppProvider


@get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


async def _main() -> None:
    ensure_bucket()
    container = make_async_container(AppProvider())
    api_router = DishkaRouter(
        path="",
        route_handlers=[TaskController, BacklogController, FocusController, WorkoutController, SettingsController],
    )
    app = Litestar(
        route_handlers=[health_check, api_router],
        cors_config=CORSConfig(
            allow_origins=["*"] if not settings.is_production else [],
        ),
        debug=True,
    )
    setup_dishka(container, app)
    await uvicorn.Server(
        uvicorn.Config(
            app,
            host="0.0.0.0",
            port=8000,
            reload=not settings.is_production,
        )
    ).serve()


if __name__ == "__main__":
    asyncio.run(_main())
