from __future__ import annotations

from functools import lru_cache

from pydantic import AnyHttpUrl, Field, SecretStr, computed_field
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
    app_timezone: str = "Europe/Moscow"

    # PostgreSQL
    db_host: str = "localhost"
    db_port: int = 5432
    db_out_port: int = 5432
    postgres_db: str = "daios"
    postgres_user: str = "daios"
    postgres_password: str = Field(..., description="PostgreSQL password")
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pool_recycle: int = 1800
    db_pool_timeout: int = 30

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_user: str = "daios"
    redis_password: str = Field(..., description="Redis password")

    # Telegram
    telegram_use_proxy: bool = Field(default=False, description="Enable SOCKS5 proxy for Telegram connections")
    telegram_socks_proxy: str = Field("", description="SOCKS5 proxy URL, e.g. socks5://user:pass@host:port")
    telegram_bot_token: str = Field(..., description="Bot token from @BotFather")
    telegram_user_id: int = Field(..., description="Your numeric Telegram user ID")
    telegram_logbot_token: str = Field("", description="Token of separate log-bot from @BotFather")
    telegram_logbot_chat_id: int = Field(0, description="Chat ID to receive log alerts (defaults to telegram_user_id when 0)")
    log_push_poll_seconds: int = Field(10, description="Interval for log-bot to poll *.error.log files for new lines")

    # LLM (OpenRouter — OpenAI-совместимый API)
    openai_api_key: SecretStr = Field(..., description="OpenRouter API key")
    openai_base_url: str = "https://openrouter.ai/api/v1"

    model_default: str = "mistralai/mistral-7b-instruct-v0.1"
    model_orchestrator: str | None = None
    model_agents: str | None = None
    model_summary: str | None = None

    @property
    def llm_model_orchestrator(self) -> str:
        return self.model_orchestrator or self.model_default

    @property
    def llm_model_agents(self) -> str:
        return self.model_agents or self.model_default

    @property
    def llm_model_summary(self) -> str:
        return self.model_summary or self.model_default

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

    # Auth (JWT)
    jwt_secret_key: SecretStr = Field(..., description="JWT signing secret")
    jwt_algorithm: str = "HS256"
    jwt_ttl_hours: int = 24

    # Admin (создаётся data-миграцией)
    admin_email: str = Field(..., description="Admin email — seeded by migration")
    admin_password: SecretStr = Field(..., description="Admin password — seeded by migration")
    admin_name: str = Field("Admin", description="Admin display name")

    # Strava
    strava_client_id: str = Field(..., description="Strava OAuth Client ID")
    strava_client_secret: SecretStr = Field(..., description="Strava OAuth Client Secret")
    strava_refresh_token: SecretStr = Field(..., description="Initial Strava refresh token")
    strava_webhook_verify_token: str = Field(..., description="Verify token for Strava webhook subscription handshake")

    # CORS
    allowed_ips: list[AnyHttpUrl] = Field(default_factory=list, description="Your server/public IP for CORS allow_origins")
    container_frontend: str = Field("daios-frontend", description="Frontend container name for CORS")

    # ── Вычисляемые поля ────────────────────────────────────────────────

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

    @computed_field
    @property
    def local_database_url(self) -> URL:
        return URL.create(
            drivername="postgresql",
            username=self.postgres_user,
            password=self.postgres_password,
            host="localhost",
            port=self.db_out_port,
            database=self.postgres_db,
        )

    @property
    def allow_origins(self) -> list[str]:
        if not self.is_production:
            return ["*"]
        origins = [f"http://{self.container_frontend}:3000"]
        origins.extend(str(ip) for ip in self.allowed_ips)
        return origins

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Lazy, cached factory — preferred over module-level `settings` in new code."""
    return Settings()


settings = Settings()
