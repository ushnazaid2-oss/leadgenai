"""
Configuration management using Pydantic Settings.
Loads from .env file with strict validation, feature flags, and env-specific overrides.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
import json


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Environment ---
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # --- Server ---
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    CORS_ORIGINS: str = '["http://localhost:8000","http://localhost:3000"]'

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from JSON string."""
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:8000"]

    # --- Tracking ---
    # Automatically use Render's external URL if available, otherwise fallback to local
    RENDER_EXTERNAL_URL: Optional[str] = None
    
    @property
    def tracking_base_url_dynamic(self) -> str:
        if self.RENDER_EXTERNAL_URL:
            return self.RENDER_EXTERNAL_URL
        return "http://localhost:8000"

    # --- Database ---
    DATABASE_URL: str = "sqlite+aiosqlite:///./leadgenai.db"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT Authentication ---
    JWT_SECRET_KEY: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- SendGrid ---
    SENDGRID_API_KEY: str = ""

    # --- SMTP ---
    SMTP_DEFAULT_HOST: str = "smtp.gmail.com"
    SMTP_DEFAULT_PORT: int = 587

    # --- WhatsApp Business API ---
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v23.0"
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""

    # --- Twilio ---
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_DEFAULT_FROM_NUMBER: str = ""

    # --- OpenAI ---
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4"

    # --- Tracking ---
    RENDER_EXTERNAL_URL: Optional[str] = None
    
    @property
    def tracking_base_url(self) -> str:
        """Dynamic tracking URL based on environment."""
        if self.RENDER_EXTERNAL_URL:
            return self.RENDER_EXTERNAL_URL
        return "http://localhost:8000"

    # --- Rate Limits ---
    EMAIL_RATE_PER_SECOND: int = 1
    EMAIL_DAILY_LIMIT_PER_ACCOUNT: int = 500
    WHATSAPP_BATCH_DELAY_SECONDS: int = 2
    MAX_CONCURRENT_CALLS: int = 5

    # --- Feature Flags ---
    FEATURE_EMAIL_ENABLED: bool = True
    FEATURE_WHATSAPP_ENABLED: bool = True
    FEATURE_CALLS_ENABLED: bool = True

    # --- Sentry ---
    SENTRY_DSN: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        if v == "change-this-in-production":
            import warnings
            warnings.warn(
                "JWT_SECRET_KEY is using default value. "
                "Set a strong secret in production!",
                stacklevel=2,
            )
        return v


# Singleton settings instance
settings = Settings()
