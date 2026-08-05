"""Application configuration with explicit environment separation.

Configuration is driven by environment variables (see ``.env.example``). Four environments are
supported (development, testing, staging, production) and three runtime safety modes
(demo, readonly_personal, controlled_action). Guardrails here prevent the Development Mac from
accidentally pointing at a production database or enabling real side effects in Demo Mode.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    development = "development"
    testing = "testing"
    staging = "staging"
    production = "production"


class RuntimeMode(str, Enum):
    demo = "demo"
    readonly_personal = "readonly_personal"
    controlled_action = "controlled_action"


class ExecutionMode(str, Enum):
    """Execution reality boundary (Section 35).

    The Development Mac always runs ``simulation``: mocked event sources, deterministic LLM
    replay, ephemeral memory, and NO real-world side effects. The Backend Mac runs ``production``:
    real event sources, local inference, persistent memory, and real (approval-gated) side
    effects. Only ``production`` execution is permitted to touch the outside world.
    """

    simulation = "simulation"
    production = "production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIFE_AGENT_",
        env_file=(".env",),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime
    env: Environment = Environment.development
    mode: RuntimeMode = RuntimeMode.demo

    # Execution reality boundary (Section 35). Defaults to the safe simulation mode so a
    # misconfigured host can never accidentally act on the real world.
    execution_mode: ExecutionMode = ExecutionMode.simulation

    # API
    api_host: str = "127.0.0.1"
    api_port: int = 8787
    cors_origins: str = ""

    # Database
    database_url: str = "sqlite:///./data/lifeagent_dev.db"

    # Paths
    data_dir: Path = Path("./data")
    documents_dir: Path = Path("./data/documents")
    log_dir: Path = Path("./logs")

    # Autonomy
    default_autonomy_level: int = 1

    # Autonomous runtime (Section 35). The continuous intelligence loop only runs on the Backend
    # Mac in production execution mode; these tune its cadence and safety.
    autonomy_loop_enabled: bool = False
    autonomy_loop_interval_seconds: float = 30.0
    autonomy_max_events_per_tick: int = 25
    notifications_enabled: bool = False

    # Feature flags (all real-world side effects default OFF)
    feature_real_email_send: bool = False
    feature_real_email_sync: bool = False
    feature_real_calendar_write: bool = False
    feature_move_email_to_spam: bool = False
    feature_real_imessage_read: bool = False
    feature_real_imessage_send: bool = False
    # Download + analyze email attachments (PDF/Word/images). Read-only, but touches network + disk.
    feature_process_documents: bool = False
    feature_remote_ai_fallback: bool = False

    # LLM routing
    llm_provider: str = "mock"
    llm_base_url: str = "http://127.0.0.1:11434"
    model_reasoning: str = "development-full"
    model_fast: str = "development-fast"
    model_embedding: str = "production-embedding"
    remote_ai_api_key: str = ""

    # Auth / secrets (dev-only defaults; production values come from the Keychain)
    dev_api_token: str = "dev-only-change-me"
    master_key: str = "dev-only-not-secret"

    # --- Email (IMAP/SMTP) — provider-agnostic; defaults target mail.com --------------
    # The account is anton.uselmann@mail.com in production; the password is injected from the
    # macOS Keychain on the Backend Mac and never stored in Git.
    email_address: str = ""
    imap_host: str = "imap.mail.com"
    imap_port: int = 993
    smtp_host: str = "smtp.mail.com"
    smtp_port: int = 587
    email_password: str = ""
    email_mailbox: str = "INBOX"

    # --- Apple Calendar (iCloud CalDAV) ------------------------------------------------
    caldav_url: str = "https://caldav.icloud.com"
    apple_id: str = ""
    apple_app_password: str = ""  # app-specific password from appleid.apple.com
    icloud_calendar_name: str = ""  # empty = default calendar

    # --- iMessage (Backend Mac only; unofficial, best-effort) --------------------------
    # Read from the local Messages SQLite store; send by driving Messages via AppleScript.
    # Requires Full Disk Access and a signed-in iMessage account on the Backend Mac.
    imessage_db_path: str = "~/Library/Messages/chat.db"

    @field_validator("default_autonomy_level")
    @classmethod
    def _clamp_autonomy(cls, v: int) -> int:
        if v < 0 or v > 3:
            # Level 4 is never a *default*; it is always explicit approval.
            raise ValueError("default_autonomy_level must be between 0 and 3")
        return v

    @model_validator(mode="after")
    def _guardrails(self) -> Settings:
        # The Development Mac must never point at a production database by default.
        if self.env == Environment.development:
            lowered = self.database_url.lower()
            if lowered.startswith(("postgres", "postgresql")) and "prod" in lowered:
                raise ValueError(
                    "Refusing to use a production-looking database URL while "
                    "LIFE_AGENT_ENV=development. This guardrail prevents the Development Mac "
                    "from touching the production database."
                )
        # Demo Mode ignores real integrations entirely.
        if self.mode == RuntimeMode.demo:
            self.feature_real_email_send = False
            self.feature_real_email_sync = False
            self.feature_real_calendar_write = False
            self.feature_move_email_to_spam = False

        # Execution reality boundary (Section 35.1 / 35.4).
        # The Development Mac (env=development) must never run in production execution mode.
        if self.env == Environment.development and self.execution_mode == ExecutionMode.production:
            raise ValueError(
                "Refusing production execution_mode while LIFE_AGENT_ENV=development. "
                "The Development Mac must run execution_mode=simulation; only the Backend Mac "
                "runs execution_mode=production."
            )
        # Production execution mode requires a production/staging environment.
        if self.execution_mode == ExecutionMode.production and self.env not in (
            Environment.production,
            Environment.staging,
        ):
            raise ValueError(
                "execution_mode=production requires LIFE_AGENT_ENV=production (or staging). "
                "This prevents real-world side effects outside the Backend Mac."
            )
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.env == Environment.production

    @property
    def is_simulation(self) -> bool:
        """True on the Development Mac: no real-world side effects are ever permitted."""
        return self.execution_mode == ExecutionMode.simulation

    @property
    def is_production_execution(self) -> bool:
        """True only on the Backend Mac, where real (approval-gated) side effects may run."""
        return self.execution_mode == ExecutionMode.production

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.documents_dir, self.log_dir):
            Path(path).mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
