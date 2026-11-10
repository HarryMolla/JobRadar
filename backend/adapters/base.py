"""
Base adapter class. All source adapters must extend this.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from backend.core.models import JobListing

logger = logging.getLogger(__name__)


@dataclass
class AdapterResult:
    source: str
    jobs: list[JobListing] = field(default_factory=list)
    success: bool = True
    error: str = ""
    duration_seconds: float = 0.0
    pages_fetched: int = 0


class BaseAdapter(ABC):
    """
    Abstract base for all job source adapters.

    Each adapter is responsible for:
    - Fetching raw job data from its source
    - Normalizing to JobListing objects
    - Handling pagination
    - Logging errors without crashing the collector

    Adapters must NOT:
    - Bypass robots.txt or ToS
    - Store secrets internally
    - Make assumptions about other adapters
    """

    # Override in subclass
    SOURCE_ID: str = "unknown"
    DISPLAY_NAME: str = "Unknown Source"
    ENABLED: bool = True

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"adapter.{self.SOURCE_ID}")

    def run(self) -> AdapterResult:
        """
        Execute the adapter. Returns AdapterResult regardless of errors.
        Never raises — errors are captured in result.
        """
        if not self.ENABLED:
            return AdapterResult(
                source=self.SOURCE_ID,
                success=False,
                error="Adapter disabled",
            )

        start = time.monotonic()
        try:
            jobs = self.fetch()
            duration = time.monotonic() - start
            self.logger.info(
                "%s: fetched %d jobs in %.1fs",
                self.SOURCE_ID, len(jobs), duration
            )
            return AdapterResult(
                source=self.SOURCE_ID,
                jobs=jobs,
                success=True,
                duration_seconds=duration,
            )
        except PermissionError as exc:
            # robots.txt or ToS violation
            self.logger.warning("%s: access denied — %s", self.SOURCE_ID, exc)
            return AdapterResult(
                source=self.SOURCE_ID,
                success=False,
                error=f"Access denied: {exc}",
                duration_seconds=time.monotonic() - start,
            )
        except Exception as exc:
            self.logger.error(
                "%s: unexpected error — %s",
                self.SOURCE_ID,
                exc,
                exc_info=True,
            )
            return AdapterResult(
                source=self.SOURCE_ID,
                success=False,
                error=str(exc),
                duration_seconds=time.monotonic() - start,
            )

    @abstractmethod
    def fetch(self) -> list[JobListing]:
        """Fetch and normalize jobs. Must be implemented by each adapter."""
        ...
