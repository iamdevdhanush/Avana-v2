import os
import secrets
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Avana V2 - Karnataka Safety Intelligence"
    VERSION: str = "2.0.0"
    DEBUG: bool = False
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str = ""

    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_POOL_RECYCLE: int = 1800
    DATABASE_SSL_MODE: str = "prefer"

    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    AI_PROVIDER: str = "openrouter"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"

    RATE_LIMIT_MAX: int = 100
    RATE_LIMIT_WINDOW: int = 60

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    CORS_ORIGINS_REGEX: str = r"https?://.*\.vercel\.app"

    KARNATAKA_BOUNDS: str = "11.5,18.0,74.0,78.5"

    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "sos@avana-safety.app"
    SOS_NOTIFICATION_EMAIL_ENABLED: bool = False

    ENABLE_INTELLIGENCE_PIPELINE: bool = True
    MOCK_INTELLIGENCE_MODE: bool = False

    def build_database_url(self) -> str:
        if self.DATABASE_URL:
            url = self.DATABASE_URL
        else:
            host = os.environ.get("POSTGRES_HOST", "")
            port = os.environ.get("POSTGRES_PORT", "5432")
            user = os.environ.get("POSTGRES_USER", "")
            password = os.environ.get("POSTGRES_PASSWORD", "")
            db = os.environ.get("POSTGRES_DB", "avana_v2")
            if not (host and user and password):
                return ""
            url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"

        if self.DATABASE_SSL_MODE != "prefer" and "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}sslmode={self.DATABASE_SSL_MODE}"
        return url

    def validate_required(self):
        errors = []
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        url = self.build_database_url()
        if not url:
            errors.append("DATABASE_URL (or POSTGRES_HOST/USER/PASSWORD) is required")
        return errors

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
