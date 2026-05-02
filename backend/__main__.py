from __future__ import annotations

import asyncio

import uvicorn
from dishka import make_async_container
from dishka.integrations.litestar import DishkaRouter, setup_dishka
from litestar import Litestar, get
from litestar.config.cors import CORSConfig

from backend.api.backlog import BacklogController
from backend.api.debug import DebugController
from backend.api.focus import FocusController
from backend.api.settings import SettingsController
from backend.api.tasks import TaskController
from backend.api.workouts import WorkoutController
from backend.auth.api.auth import AuthController
from backend.auth.guards import jwt_auth_guard
from backend.core.config import settings
from backend.core.minio_client import ensure_bucket
from backend.core.providers import AppProvider


@get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


async def _main() -> None:
    ensure_bucket()
    container = make_async_container(AppProvider())
    protected_router = DishkaRouter(
        path="",
        guards=[jwt_auth_guard],
        route_handlers=[TaskController, BacklogController, FocusController, WorkoutController, SettingsController, DebugController],
    )
    auth_router = DishkaRouter(
        path="",
        route_handlers=[AuthController],
    )
    app = Litestar(
        route_handlers=[health_check, auth_router, protected_router],
        cors_config=CORSConfig(
            allow_origins=settings.allow_origins,
        ),
        debug=not settings.is_production,
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
