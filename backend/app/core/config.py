"""
Centralized application configuration.

All environment variables are loaded and validated here via pydantic-settings.
No other module should call os.environ directly — import `settings` instead.
This gives us one auditable place where secrets enter the application.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "AI Marketing Agent"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    # --- Security ---
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Database ---
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "ai_marketing_agent"
    DATABASE_URL: str = ""

    # --- Redis ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_URL: str = ""

    # --- Celery ---
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- AI Providers ---
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_AI_PROVIDER: str = "anthropic"

    # --- S3-Compatible Storage ---
    S3_ENDPOINT_URL: str = ""
    S3_ACCESS_KEY_ID: str = ""
    S3_SECRET_ACCESS_KEY: str = ""
    S3_BUCKET_NAME: str = "ai-marketing-agent-assets"
    S3_REGION: str = "us-east-1"

    # --- Rate limiting ---
    RATE_LIMIT_DEFAULT: str = "100/minute"

    # --- Field-level encryption for stored third-party credentials ---
    CREDENTIALS_ENCRYPTION_KEY: str = ""

    # --- Outbound email (password reset, email verification) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    # STARTTLS is the common case for port 587 (Gmail, SES, Mailgun, etc.);
    # set false only for local dev catchers like Mailhog/MailCatcher that
    # don't speak TLS.
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = "no-reply@ai-marketing-agent.local"
    SMTP_FROM_NAME: str = "AI Marketing Agent"

    # Base URL of the deployed frontend — used to build links inside emails
    # (verify-email, reset-password). Never used for anything else; this is
    # the one place a frontend URL belongs in backend config.
    FRONTEND_BASE_URL: str = "http://localhost:3000"

    # --- Token expiry ---
    EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30

    # --- Social platform OAuth (Week 6) ---
    # Each pair is empty by default. app/oauth/registry.py checks these at
    # connect-flow start and returns a clear "this platform isn't
    # configured on this deployment" error rather than attempting an
    # OAuth handshake with an empty client_id, which platforms would
    # reject with a much more confusing error deep in the flow.
    FACEBOOK_CLIENT_ID: str = ""
    FACEBOOK_CLIENT_SECRET: str = ""
    INSTAGRAM_CLIENT_ID: str = ""
    INSTAGRAM_CLIENT_SECRET: str = ""
    LINKEDIN_CLIENT_ID: str = ""
    LINKEDIN_CLIENT_SECRET: str = ""
    X_CLIENT_ID: str = ""
    X_CLIENT_SECRET: str = ""
    TIKTOK_CLIENT_ID: str = ""
    TIKTOK_CLIENT_SECRET: str = ""
    YOUTUBE_CLIENT_ID: str = ""
    YOUTUBE_CLIENT_SECRET: str = ""

    # Base URL this backend is reachable at — used to build the
    # redirect_uri sent to each platform's OAuth authorize endpoint. Must
    # exactly match a redirect URI registered in each platform's own app
    # dashboard, or the platform will reject the callback.
    OAUTH_REDIRECT_BASE_URL: str = "http://localhost:8000"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def assemble_db_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        return (
            f"postgresql+psycopg2://{data.get('POSTGRES_USER')}:"
            f"{data.get('POSTGRES_PASSWORD')}@{data.get('POSTGRES_HOST')}:"
            f"{data.get('POSTGRES_PORT')}/{data.get('POSTGRES_DB')}"
        )

    @field_validator("REDIS_URL", mode="before")
    @classmethod
    def assemble_redis_url(cls, v: str, info) -> str:
        if v:
            return v
        data = info.data
        return f"redis://{data.get('REDIS_HOST')}:{data.get('REDIS_PORT')}/{data.get('REDIS_DB')}"


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — .env is read once per process."""
    return Settings()


settings = get_settings()
