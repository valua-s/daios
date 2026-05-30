from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.content_agent import ContentAgent
from backend.agents.context_agent import ContextAgent
from backend.agents.evening_agent import EveningAgent
from backend.agents.orchestrator import Orchestrator
from backend.agents.task_agent import TaskAgent
from backend.agents.workout_agent import WorkoutAgent
from backend.auth.service.auth_service import AuthService
from backend.core.config import Settings, get_settings
from backend.core.db import AsyncSessionFactory
from backend.core.redis import create_redis
from backend.integrations.bus_schedule import BusScheduleParser
from backend.integrations.google_sheets import GoogleSheetsClient
from backend.integrations.news import NewsClient
from backend.integrations.rss import RSSParser
from backend.integrations.telegram import TelegramNotifier
from backend.integrations.vk import VKClient
from backend.integrations.weather import WeatherClient
from backend.integrations.youtube import YouTubeClient
from backend.repositories.backlog_repo import BacklogRepository
from backend.repositories.completed_workout_repo import (
    CompletedWorkoutRepository,
)
from backend.repositories.focus_repo import FocusRepository
from backend.repositories.note_repo import NoteItemRepository, NoteRepository
from backend.repositories.task_repo import TaskRepository
from backend.services.content_service import ContentService
from backend.services.focus_resolver import FocusResolver
from backend.services.focus_service import FocusService
from backend.services.llm_service import LLMService
from backend.services.note_service import NoteService
from backend.services.settings_service import SettingsService
from backend.services.task_service import TaskService
from backend.services.wakeup_planner import WakeupPlanner
from backend.services.workout_service import WorkoutService


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:  # noqa: PLR6301
        return get_settings()

    @provide(scope=Scope.APP)
    async def get_redis(self) -> AsyncIterator[Redis]:  # noqa: PLR6301
        client = create_redis()
        try:
            yield client
        finally:
            await client.aclose()

    @provide(scope=Scope.APP)
    async def get_http_client(self) -> AsyncIterator[httpx.AsyncClient]:  # noqa: PLR6301
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client

    @provide(scope=Scope.APP)
    def get_sheets_client(self) -> GoogleSheetsClient:  # noqa: PLR6301
        return GoogleSheetsClient()

    @provide(scope=Scope.APP)
    def get_telegram_notifier(self) -> TelegramNotifier:  # noqa: PLR6301
        return TelegramNotifier()

    @provide(scope=Scope.APP)
    def get_weather_client(self, http_client: httpx.AsyncClient) -> WeatherClient:  # noqa: PLR6301
        return WeatherClient(http_client)

    @provide(scope=Scope.APP)
    def get_bus_parser(self, http_client: httpx.AsyncClient) -> BusScheduleParser:  # noqa: PLR6301
        return BusScheduleParser(http_client)

    @provide(scope=Scope.APP)
    def get_rss_parser(self) -> RSSParser:  # noqa: PLR6301
        return RSSParser()

    @provide(scope=Scope.APP)
    def get_youtube_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> YouTubeClient:  # noqa: PLR6301
        return YouTubeClient(http_client, cfg.youtube_api_key)

    @provide(scope=Scope.APP)
    def get_vk_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> VKClient:  # noqa: PLR6301
        return VKClient(http_client, cfg.vk_access_token)

    @provide(scope=Scope.APP)
    def get_news_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> NewsClient:  # noqa: PLR6301
        return NewsClient(http_client, cfg.news_api_key)

    @provide(scope=Scope.APP)
    def get_llm_service(self, cfg: Settings) -> LLMService:  # noqa: PLR6301
        return LLMService(cfg)

    @provide(scope=Scope.REQUEST)
    async def get_session(self) -> AsyncIterator[AsyncSession]:  # noqa: PLR6301
        session = AsyncSessionFactory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

    @provide(scope=Scope.REQUEST)
    def get_auth_service(self, session: AsyncSession, cfg: Settings) -> AuthService:  # noqa: PLR6301
        return AuthService(
            session=session,
            secret_key=cfg.jwt_secret_key.get_secret_value(),
            algorithm=cfg.jwt_algorithm,
        )

    @provide(scope=Scope.REQUEST)
    def get_task_repo(self, session: AsyncSession) -> TaskRepository:  # noqa: PLR6301
        return TaskRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_backlog_repo(self, session: AsyncSession) -> BacklogRepository:  # noqa: PLR6301
        return BacklogRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_focus_repo(self, session: AsyncSession) -> FocusRepository:  # noqa: PLR6301
        return FocusRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_note_repo(self, session: AsyncSession) -> NoteRepository:  # noqa: PLR6301
        return NoteRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_note_item_repo(self, session: AsyncSession) -> NoteItemRepository:  # noqa: PLR6301
        return NoteItemRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_note_service(self, session: AsyncSession) -> NoteService:  # noqa: PLR6301
        return NoteService(session)

    @provide(scope=Scope.REQUEST)
    def get_focus_service(self, session: AsyncSession) -> FocusService:  # noqa: PLR6301
        return FocusService(session)

    @provide(scope=Scope.REQUEST)
    def get_task_service(self, session: AsyncSession) -> TaskService:  # noqa: PLR6301
        return TaskService(session)

    @provide(scope=Scope.REQUEST)
    def get_settings_service(self, session: AsyncSession, redis: Redis) -> SettingsService:  # noqa: PLR6301
        return SettingsService(session, redis)

    @provide(scope=Scope.REQUEST)
    def get_workout_service(  # noqa: PLR6301
        self,
        session: AsyncSession,
        sheets_client: GoogleSheetsClient,
    ) -> WorkoutService:
        return WorkoutService(session, sheets_client)

    @provide(scope=Scope.REQUEST)
    def get_completed_workout_repo(self, session: AsyncSession) -> CompletedWorkoutRepository:  # noqa: PLR6301
        return CompletedWorkoutRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_context_agent(  # noqa: PLR6301
        self,
        weather_client: WeatherClient,
        bus_parser: BusScheduleParser,
    ) -> ContextAgent:
        return ContextAgent(weather_client, bus_parser)

    @provide(scope=Scope.REQUEST)
    def get_task_agent(self, task_service: TaskService) -> TaskAgent:  # noqa: PLR6301
        return TaskAgent(task_service)

    @provide(scope=Scope.REQUEST)
    def get_workout_agent(self, workout_service: WorkoutService) -> WorkoutAgent:  # noqa: PLR6301
        return WorkoutAgent(workout_service)

    @provide(scope=Scope.REQUEST)
    def get_content_service(  # noqa: PLR6301
        self,
        session: AsyncSession,
        rss_parser: RSSParser,
        youtube_client: YouTubeClient,
        vk_client: VKClient,
        news_client: NewsClient,
    ) -> ContentService:
        return ContentService(session, rss_parser, youtube_client, vk_client, news_client)

    @provide(scope=Scope.REQUEST)
    def get_focus_resolver(  # noqa: PLR6301
        self,
        focus_service: FocusService,
        settings_service: SettingsService,
    ) -> FocusResolver:
        return FocusResolver(focus_service, settings_service)

    @provide(scope=Scope.REQUEST)
    def get_content_agent(  # noqa: PLR6301
        self,
        content_service: ContentService,
        focus_resolver: FocusResolver,
        llm_service: LLMService,
    ) -> ContentAgent:
        return ContentAgent(content_service, focus_resolver, llm_service)

    @provide(scope=Scope.REQUEST)
    def get_evening_agent(self, task_service: TaskService) -> EveningAgent:  # noqa: PLR6301
        return EveningAgent(task_service)

    @provide(scope=Scope.REQUEST)
    def get_wakeup_planner(  # noqa: PLR6301
        self,
        workout_service: WorkoutService,
        weather_client: WeatherClient,
        settings_service: SettingsService,
    ) -> WakeupPlanner:
        return WakeupPlanner(workout_service, weather_client, settings_service)

    @provide(scope=Scope.REQUEST)
    def get_orchestrator(  # noqa: PLR6301
        self,
        context_agent: ContextAgent,
        workout_agent: WorkoutAgent,
        task_agent: TaskAgent,
        content_agent: ContentAgent,
        evening_agent: EveningAgent,
        task_service: TaskService,
        notifier: TelegramNotifier,
        wakeup_planner: WakeupPlanner,
    ) -> Orchestrator:
        return Orchestrator(
            context_agent, workout_agent, task_agent,
            content_agent, evening_agent, task_service, notifier,
            wakeup_planner,
        )
