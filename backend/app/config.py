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

    # AI Auto-Takeoff (Sprint AI-01) — providers wrapped behind app.services.ai_models
    # so swapping models is a config change, not a code change.
    ai_vision_provider: str = "anthropic"
    ai_vision_model: str = "claude-sonnet-4-5"
    ai_embedding_provider: str = "openai"
    ai_embedding_model: str = "text-embedding-3-small"
    ai_llm_provider: str = "anthropic"
    ai_llm_model: str = "claude-sonnet-4-5"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    #: Daily per-org spend cap for the abuse circuit breaker. Default is
    #: deliberately high (~100x typical run cost) -- this is *abuse* protection,
    #: not a per-user limit. Customer-facing usage caps do not exist; AI is
    #: included in the subscription.
    ai_daily_cost_circuit_breaker_cents_per_org: int = 5000

    # AI Auto-Takeoff (Sprint AI-02) — Stage 1 (title block) + Stage 2
    # (sheet classification) tunables. Heuristics-first: a vision/LLM call
    # only happens when the deterministic pass falls below the threshold.
    #: Path to the ``tesseract`` binary for the OCR fallback in Stage 1. Empty
    #: means resolve via PATH (Linux Celery workers); set explicitly on Windows
    #: dev boxes (e.g. ``C:\\Program Files\\Tesseract-OCR\\tesseract.exe``).
    #: When tesseract is missing the OCR call returns "" and the pipeline
    #: gracefully degrades to "no title for this sheet".
    ai_tesseract_cmd: str = ""
    #: Below this confidence the lexical sheet classifier escalates to the
    #: vision model (Stage 2). The "uninteresting sheet" skip-list (cover,
    #: index, spec) bypasses the escalation even when below threshold so we
    #: never pay for vision on a clearly-non-plan sheet.
    ai_classification_confidence_threshold: float = 0.7
    #: Number of sheet thumbnails packed into a single multimodal vision
    #: classification call. 6 is a balance between prompt clarity and
    #: per-call cost; raise cautiously -- the schema gets messy past ~10.
    ai_vision_classify_batch_size: int = 6
    #: Anthropic Claude Sonnet pricing (cents per 1k tokens). Config-driven so
    #: pricing changes don't require a deploy. Defaults match the published
    #: Sonnet 4.5 rates as of 2026-04 ($3/Mtok input, $15/Mtok output).
    ai_anthropic_vision_input_per_1k_cents: float = 0.3
    ai_anthropic_vision_output_per_1k_cents: float = 1.5

    # AI-02b: Title-block auto-name flow ─────────────────────────────────────
    #: Master kill-switch. When false, the API endpoint returns 503 and the
    #: frontend hides the button. Lets ops disable the feature per-deployment
    #: without code changes if early users hit edge cases on a particular
    #: plan set.
    ai_auto_name_enabled: bool = True
    #: Title-block region heuristic: bottom-right corner box dimensions in
    #: PDF user-space points. ~350x350 pts ~= 4.86" x 4.86" -- covers the
    #: typical title block on D-size and ARCH-D sheets without grabbing
    #: notes from the right margin.
    ai_title_block_box_width_pts: float = 350.0
    ai_title_block_box_height_pts: float = 350.0
    #: DPI for the OCR fallback render. Bumped from the default 144 in
    #: ``app/utils/pdf.py`` because title-block fonts are small (~6-8pt) and
    #: 200 DPI is the sweet spot for Tesseract on that text size.
    ai_title_block_clip_dpi: int = 200
    #: Below this confidence (or when a field is null) the heuristic parser
    #: escalates to the LLM cleanup pass.
    ai_title_block_llm_min_confidence: float = 0.7
    #: LLM provider + model for the title-block cleanup pass. Decoupled from
    #: the global ``ai_llm_provider`` (Anthropic) on purpose: title-block
    #: parsing is pure structured-text extraction where gpt-4o-mini's strict
    #: JSON schema enforcement is the right tool. Other LLM tasks (AI-04
    #: condition naming) keep using Anthropic.
    ai_title_block_llm_provider: str = "openai"
    ai_title_block_llm_model: str = "gpt-4o-mini"
    #: OpenAI gpt-4o-mini pricing (cents per 1k tokens). Defaults match the
    #: published rates as of 2026-04 ($0.15/Mtok input, $0.60/Mtok output).
    ai_openai_llm_input_per_1k_cents: float = 0.015
    ai_openai_llm_output_per_1k_cents: float = 0.06
    #: Hard timeout per OpenAI call from the worker. Keeps a hung provider
    #: from stalling the whole re-extract task.
    ai_openai_llm_timeout_s: float = 20.0
    ai_openai_llm_max_retries: int = 2

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
