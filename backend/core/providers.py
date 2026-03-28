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
from backend.core.config import Settings, settings
from backend.core.db import AsyncSessionFactory
from backend.core.redis import redis_client
from backend.integrations.bus_schedule import BusScheduleParser
from backend.integrations.google_sheets import GoogleSheetsClient
from backend.integrations.news import NewsClient
from backend.integrations.rss import RSSParser
from backend.integrations.telegram import TelegramNotifier
from backend.integrations.vk import VKClient
from backend.integrations.weather import WeatherClient
from backend.integrations.youtube import YouTubeClient
from backend.repositories.backlog_repo import BacklogRepository
from backend.repositories.focus_repo import FocusRepository
from backend.repositories.task_repo import TaskRepository
from backend.services.content_service import ContentService
from backend.services.focus_service import FocusService
from backend.services.settings_service import SettingsService
from backend.services.task_service import TaskService
from backend.services.workout_service import WorkoutService


class AppProvider(Provider):
    @provide(scope=Scope.APP)
    def get_settings(self) -> Settings:
        return settings

    @provide(scope=Scope.APP)
    def get_redis(self) -> Redis:
        return redis_client

    @provide(scope=Scope.APP)
    async def get_http_client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            yield client

    @provide(scope=Scope.APP)
    def get_sheets_client(self) -> GoogleSheetsClient:
        return GoogleSheetsClient()

    @provide(scope=Scope.APP)
    def get_telegram_notifier(self) -> TelegramNotifier:
        return TelegramNotifier()

    @provide(scope=Scope.APP)
    def get_weather_client(self, http_client: httpx.AsyncClient) -> WeatherClient:
        return WeatherClient(http_client)

    @provide(scope=Scope.APP)
    def get_bus_parser(self, http_client: httpx.AsyncClient) -> BusScheduleParser:
        return BusScheduleParser(http_client)

    @provide(scope=Scope.APP)
    def get_rss_parser(self) -> RSSParser:
        return RSSParser()

    @provide(scope=Scope.APP)
    def get_youtube_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> YouTubeClient:
        return YouTubeClient(http_client, cfg.youtube_api_key)

    @provide(scope=Scope.APP)
    def get_vk_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> VKClient:
        return VKClient(http_client, cfg.vk_access_token)

    @provide(scope=Scope.APP)
    def get_news_client(self, http_client: httpx.AsyncClient, cfg: Settings) -> NewsClient:
        return NewsClient(http_client, cfg.news_api_key)

    @provide(scope=Scope.REQUEST)
    async def get_session(self) -> AsyncIterator[AsyncSession]:
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
    def get_task_repo(self, session: AsyncSession) -> TaskRepository:
        return TaskRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_backlog_repo(self, session: AsyncSession) -> BacklogRepository:
        return BacklogRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_focus_repo(self, session: AsyncSession) -> FocusRepository:
        return FocusRepository(session)

    @provide(scope=Scope.REQUEST)
    def get_focus_service(self, session: AsyncSession) -> FocusService:
        return FocusService(session)

    @provide(scope=Scope.REQUEST)
    def get_task_service(self, session: AsyncSession) -> TaskService:
        return TaskService(session)

    @provide(scope=Scope.REQUEST)
    def get_settings_service(self, session: AsyncSession, redis: Redis) -> SettingsService:
        return SettingsService(session, redis)

    @provide(scope=Scope.REQUEST)
    def get_workout_service(
        self,
        session: AsyncSession,
        sheets_client: GoogleSheetsClient,
    ) -> WorkoutService:
        return WorkoutService(session, sheets_client)

    @provide(scope=Scope.REQUEST)
    def get_context_agent(
        self,
        weather_client: WeatherClient,
        bus_parser: BusScheduleParser,
    ) -> ContextAgent:
        return ContextAgent(weather_client, bus_parser)

    @provide(scope=Scope.REQUEST)
    def get_task_agent(self, task_service: TaskService) -> TaskAgent:
        return TaskAgent(task_service)

    @provide(scope=Scope.REQUEST)
    def get_workout_agent(self, workout_service: WorkoutService) -> WorkoutAgent:
        return WorkoutAgent(workout_service)

    @provide(scope=Scope.REQUEST)
    def get_content_service(
        self,
        session: AsyncSession,
        rss_parser: RSSParser,
        youtube_client: YouTubeClient,
        vk_client: VKClient,
        news_client: NewsClient,
    ) -> ContentService:
        return ContentService(session, rss_parser, youtube_client, vk_client, news_client)

    @provide(scope=Scope.REQUEST)
    def get_content_agent(
        self,
        content_service: ContentService,
        focus_service: FocusService,
    ) -> ContentAgent:
        return ContentAgent(content_service, focus_service)

    @provide(scope=Scope.REQUEST)
    def get_evening_agent(self, task_service: TaskService) -> EveningAgent:
        return EveningAgent(task_service)

    @provide(scope=Scope.REQUEST)
    def get_orchestrator(
        self,
        context_agent: ContextAgent,
        workout_agent: WorkoutAgent,
        task_agent: TaskAgent,
        content_agent: ContentAgent,
        evening_agent: EveningAgent,
        task_service: TaskService,
        notifier: TelegramNotifier,
    ) -> Orchestrator:
        return Orchestrator(
            context_agent, workout_agent, task_agent,
            content_agent, evening_agent, task_service, notifier,
        )
