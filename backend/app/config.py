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

    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_KEY: Optional[str] = None

    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GEMINI_API_KEY: Optional[str] = None

    RATE_LIMIT_MAX: int = 100
    RATE_LIMIT_WINDOW: int = 60

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    KARNATAKA_BOUNDS: str = "11.5,18.0,74.0,78.5"

    SENDGRID_API_KEY: Optional[str] = None
    SENDGRID_FROM_EMAIL: str = "sos@avana-safety.app"
    SOS_NOTIFICATION_EMAIL_ENABLED: bool = False

    ENABLE_INTELLIGENCE_PIPELINE: bool = True

    def validate_required(self):
        errors = []
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            errors.append("SECRET_KEY must be at least 32 characters")
        if not self.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        return errors

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
