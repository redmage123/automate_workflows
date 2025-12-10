"""Application configuration"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    # API
    API_V1_PREFIX: str = "/api"
    PROJECT_NAME: str = "Automation Platform API"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Security
    JWT_SECRET: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 1440  # 24 hours
    ENCRYPTION_KEY: str  # Fernet key for encrypting sensitive data

    # Database
    DATABASE_URL: str

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    BACKEND_URL: str = "http://localhost:8000"

    # Stripe
    STRIPE_SECRET_KEY: str
    STRIPE_PUBLISHABLE_KEY: str
    STRIPE_WEBHOOK_SECRET: str

    # S3
    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    S3_REGION: str = "us-east-1"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email
    RESEND_API_KEY: Optional[str] = None
    POSTMARK_TOKEN: Optional[str] = None

    # n8n
    N8N_DEFAULT_BASE_URL: str = "http://localhost:5678"
    N8N_DEFAULT_API_KEY: str = ""

    # Observability
    SENTRY_DSN: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @property
    def async_database_url(self) -> str:
        """Get async database URL"""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


settings = Settings()
