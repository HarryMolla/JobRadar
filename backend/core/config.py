"""
Central configuration loader for JobRadar.
Reads from environment variables (GitHub Actions Secrets / local .env).
Never hardcodes secrets.
"""
from __future__ import annotations

import os
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
    # Repository state storage
    state_file_path: Path = field(
        default_factory=lambda: Path(os.environ.get("STATE_FILE_PATH", "data/job_state.json"))
    )

    # Gmail API (OAuth 2.0)
    notification_email: str = field(
        default_factory=lambda: os.environ.get("NOTIFICATION_EMAIL", "")
    )
    gmail_credentials_json: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_JSON", "")
    )
    gmail_token_json: str = field(
        default_factory=lambda: os.environ.get("GMAIL_TOKEN_JSON", "")
    )

    # Telegram (optional fallback notification)
    telegram_bot_token: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.environ.get("TELEGRAM_CHAT_ID", "")
    )

    # Collector thresholds
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
        """Return list of warnings or missing configuration items."""
        warnings = []
        if not self.has_gmail and not self.has_telegram:
            warnings.append(
                "Neither Gmail (GMAIL_CREDENTIALS_JSON/GMAIL_TOKEN_JSON) nor Telegram is configured. "
                "Jobs will be collected and stored in data/job_state.json, but email alerts will be skipped."
            )
        return warnings

    @property
    def has_gmail(self) -> bool:
        return bool(self.gmail_credentials_json and self.gmail_token_json and self.notification_email)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config()
    return _config
