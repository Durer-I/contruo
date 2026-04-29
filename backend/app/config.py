from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Supabase
    supabase_url: str = ""

    @field_validator("supabase_url", mode="before")
    @classmethod
    def strip_supabase_url_trailing_slash(cls, v: object) -> object:
        if isinstance(v, str) and v:
            return v.rstrip("/")
        return v
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/contruo"
    #: Dev-only escape hatch if TLS verification fails (e.g. HTTPS inspection). Never false in production.
    database_ssl_verify: bool = True

    # Liveblocks
    liveblocks_secret_key: str = ""

    # DodoPayments
    dodopayments_api_key: str = ""
    dodopayments_webhook_secret: str = ""
    #: `test_mode` or `live_mode` per DodoPayments SDK
    dodopayments_environment: str = "test_mode"
    #: Annual subscription product id from DodoPayments dashboard (checkout + plan changes).
    dodopayments_subscription_product_id: str = ""
    #: When set, pure per-seat: base `quantity` 1 + Seat add-on `quantity` = paid seats (min 1 at checkout).
    dodopayments_seat_addon_id: str = ""

    # Redis / Celery — must be supplied via environment in any deployed env.
    redis_url: str = "redis://localhost:6379/0"

    # Email
    email_provider: str = "resend"
    email_api_key: str = ""
    email_from: str = "noreply@contruo.com"

    # App
    app_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    environment: str = "development"
    #: If true, Supabase Auth users created via /register are email-confirmed immediately (no confirmation email).
    #: Development also auto-confirms unless you set ENVIRONMENT=production without this flag.
    auth_auto_confirm_registered_users: bool = False

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def assert_production_secrets(self) -> None:
        """Fail fast on startup if required secrets are missing/insecure in prod."""
        if not self.is_production:
            return
        problems: list[str] = []
        if not self.redis_url or self.redis_url.startswith("redis://localhost"):
            problems.append("REDIS_URL must be set to a non-localhost URL")
        if not self.dodopayments_webhook_secret:
            problems.append("DODOPAYMENTS_WEBHOOK_SECRET must be set")
        if not self.supabase_service_role_key:
            problems.append("SUPABASE_SERVICE_ROLE_KEY must be set")
        if "postgres:postgres@localhost" in self.database_url:
            problems.append("DATABASE_URL must not use the local default password")
        if problems:
            raise RuntimeError(
                "Refusing to start in production with insecure config:\n  - "
                + "\n  - ".join(problems)
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
