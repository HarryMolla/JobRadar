"""
Central configuration loader.
Reads from environment variables (GitHub Secrets / .env locally).
Never hardcodes secrets.
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load .env file if present (local dev only)
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class Config:
    # Supabase
    supabase_url: str = field(default_factory=lambda: os.environ.get("SUPABASE_URL", ""))
    supabase_anon_key: str = field(default_factory=lambda: os.environ.get("SUPABASE_ANON_KEY", ""))
    supabase_service_role_key: str = field(
        default_factory=lambda: os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    )

    # Gmail
    notification_email: str = field(
        default_factory=lambda: os.environ.get("NOTIFICATION_EMAIL", "")
    )
    gmail_credentials_json: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_JSON", "")
    )
    gmail_token_json: str = field(
        default_factory=lambda: os.environ.get("GMAIL_TOKEN_JSON", "")
    )

    # Telegram (optional fallback)
    telegram_bot_token: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", "")
    )

    # Collector tuning
    min_match_score: int = field(
        default_factory=lambda: int(os.environ.get("MIN_MATCH_SCORE", "40"))
    )
    notification_min_score: int = field(
        default_factory=lambda: int(os.environ.get("NOTIFICATION_MIN_SCORE", "50"))
    )
    max_jobs_per_source: int = field(
        default_factory=lambda: int(os.environ.get("MAX_JOBS_PER_SOURCE", "100"))
    )
    request_timeout: int = field(
        default_factory=lambda: int(os.environ.get("REQUEST_TIMEOUT", "30"))
    )
    request_delay: float = field(
        default_factory=lambda: float(os.environ.get("REQUEST_DELAY_SECONDS", "2.0"))
    )

    def validate(self) -> list[str]:
        """Return list of missing critical configuration items."""
        errors = []
        if not self.supabase_url:
            errors.append("SUPABASE_URL is not set")
        if not self.supabase_service_role_key and not self.supabase_anon_key:
            errors.append("Neither SUPABASE_SERVICE_ROLE_KEY nor SUPABASE_ANON_KEY is set")
        return errors

    @property
    def has_gmail(self) -> bool:
        return bool(self.gmail_credentials_json and self.notification_email)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def supabase_key(self) -> str:
        """Prefer service role key for backend; fall back to anon."""
        return self.supabase_service_role_key or self.supabase_anon_key


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
