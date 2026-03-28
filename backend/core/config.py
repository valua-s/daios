from __future__ import annotations

from pydantic import AnyHttpUrl, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine.url import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    docker: bool = False
    # App
    app_env: str = "development"
    secret_key: str = Field(..., description="Application secret key")
    app_timezone: str = "Europe/Moscow"

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_out_port: int = 5432
    postgres_db: str = "daios"
    postgres_user: str = "daios"
    postgres_password: str = Field(..., description="PostgreSQL password")

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_user: str = "daios"
    redis_password: str = Field(..., description="Redis password")

    # Minio
    minio_host: str = "localhost"
    minio_port: int = 9000
    minio_access_key: str = "daios_minio"
    minio_secret_key: str = Field(..., description="Minio secret key")
    minio_bucket_media: str = "daios-media"
    minio_secure: bool = False

    # Telegram
    telegram_use_proxy: bool = Field(default=False, description="Enable SOCKS5 proxy for Telegram connections")
    telegram_socks_proxy: str = Field("", description="SOCKS5 proxy URL, e.g. socks5://user:pass@host:port")
    telegram_bot_token: str = Field(..., description="Bot token from @BotFather")
    telegram_user_id: int = Field(..., description="Your numeric Telegram user ID")

    # LLM (OpenRouter — OpenAI-совместимый API)
    openai_api_key: str = Field(..., description="OpenRouter API key")
    openai_base_url: str = "https://openrouter.ai/api/v1"

    model_orchestrator: str = "mistralai/mistral-7b-instruct"
    model_agents: str = "mistralai/mistral-7b-instruct"
    model_summary: str = "mistralai/mistral-7b-instruct"

    # Google Sheets
    google_credentials_file: str = "secrets/credentials.json"
    google_sheets_workout_id: str = Field(..., description="Spreadsheet ID from URL")

    # OpenWeatherMap
    openweather_api_key: str = Field(..., description="OpenWeatherMap API key")
    openweather_city: str = "Almaty"

    # Bus schedule
    bus_schedule_url: str = Field(..., description="URL страницы с расписанием автобусов")

    # YouTube Data API v3
    youtube_api_key: str = Field("", description="YouTube Data API v3 key")

    # VKontakte API
    vk_access_token: str = Field("", description="VK access token")

    # NewsAPI
    news_api_key: str = Field("", description="NewsAPI.org API key")

    # CORS
    allows_ips: list[AnyHttpUrl] = Field(default_factory=list, description="Your server/public IP for CORS allow_origins")
    container_frontend: str = Field("daios-frontend", description="Frontend container name for CORS")

    # ── Вычисляемые поля ────────────────────────────────────────────────

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    @computed_field
    @property
    def database_url(self) -> URL:
        """SQLAlchemy URL object — передаётся напрямую в create_async_engine."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.db_host if self.docker else "localhost",
            port=self.db_port if self.docker else self.db_out_port,
            database=self.postgres_db,
        )

    @property
    def allow_origins(self) -> list[str]:
        if not self.is_production:
            return ["*"]
        origins = [f"http://{self.container_frontend}:3000"]
        origins.extend(str(ip) for ip in self.allows_ips)
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# Singleton — импортируется во всём проекте
settings = Settings()
