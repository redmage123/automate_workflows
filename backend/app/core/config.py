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

    # Stripe Subscription Plans
    # WHY: Price IDs map our plans to Stripe products for billing
    STRIPE_PRICE_PRO_MONTHLY: Optional[str] = None  # price_xxx
    STRIPE_PRICE_PRO_YEARLY: Optional[str] = None  # price_xxx
    STRIPE_PRICE_ENTERPRISE_MONTHLY: Optional[str] = None  # price_xxx
    STRIPE_PRICE_ENTERPRISE_YEARLY: Optional[str] = None  # price_xxx
    STRIPE_TRIAL_DAYS: int = 14  # Trial period for new subscriptions

    # S3 / AWS
    S3_ENDPOINT: Optional[str] = None
    S3_ACCESS_KEY: Optional[str] = None
    S3_SECRET_KEY: Optional[str] = None
    S3_BUCKET: str = "automation-platform-documents"
    S3_REGION: str = "us-east-1"

    # AWS (alternative config for boto3)
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "automation-platform-documents"  # Alias for S3_BUCKET

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Email
    RESEND_API_KEY: Optional[str] = None
    POSTMARK_TOKEN: Optional[str] = None

    # n8n
    N8N_DEFAULT_BASE_URL: str = "http://localhost:5678"
    N8N_DEFAULT_API_KEY: str = ""

    # Slack Notifications
    SLACK_WEBHOOK_URL: Optional[str] = None
    SLACK_WEBHOOK_ENABLED: bool = False

    # OpenAI API (for natural language workflow generation)
    # WHY: GPT is used to convert plain text workflow descriptions to n8n JSON
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-5.2"  # Default model for workflow generation (GPT-5.2 is latest)

    # Observability
    SENTRY_DSN: Optional[str] = None

    # CORS
    # WHY: Allow frontend from multiple ports during development
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5100",
        "http://localhost:5101",
        "http://localhost:5173",
        "http://127.0.0.1:5100",
        "http://127.0.0.1:5101",
        "http://127.0.0.1:5173",
        "http://176.9.99.103:5100",
        "http://176.9.99.103:5101",
        "http://176.9.99.103:5173",
    ]

    # Google OAuth
    # WHY: OAuth enables social login for better UX and security
    GOOGLE_OAUTH_CLIENT_ID: Optional[str] = None
    GOOGLE_OAUTH_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: Optional[str] = None  # e.g., http://localhost:8000/api/auth/oauth/google/callback

    @property
    def google_oauth_enabled(self) -> bool:
        """
        Check if Google OAuth is properly configured.

        WHY: OAuth requires all three settings. If any are missing,
        the Google login button should be hidden in the UI.
        """
        return all([
            self.GOOGLE_OAUTH_CLIENT_ID,
            self.GOOGLE_OAUTH_CLIENT_SECRET,
            self.GOOGLE_OAUTH_REDIRECT_URI,
        ])

    @property
    def async_database_url(self) -> str:
        """Get async database URL"""
        return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")


settings = Settings()
