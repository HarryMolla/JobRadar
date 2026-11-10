"""
RemoteOK adapter.
Uses the official JSON API: https://remoteok.com/api
Rate limit: be respectful, min 2s between requests.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

API_URL = "https://remoteok.com/api"


class RemoteOKAdapter(BaseAdapter):
    SOURCE_ID = "remoteok"
    DISPLAY_NAME = "Remote OK"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        self.logger.info("Fetching from RemoteOK API")
        data = get_json(
            API_URL,
            headers={"Accept": "application/json"},
            check_robots=False,  # Public API, robots.txt allows bots
        )

        # First item is a legal disclaimer dict, skip it
        jobs_raw = [item for item in data if isinstance(item, dict) and item.get("id")]
        jobs = []
        for raw in jobs_raw:
            try:
                job = self._normalize(raw)
                if job:
                    jobs.append(job)
            except Exception as exc:
                self.logger.debug("Failed to normalize job %s: %s", raw.get("id"), exc)

        self.logger.info("RemoteOK: %d jobs parsed", len(jobs))
        return jobs

    def _normalize(self, raw: dict) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        url = raw.get("url", "")
        if not url:
            url = f"https://remoteok.com/remote-jobs/{job_id}"
        title = raw.get("position", "")
        company = raw.get("company", "")
        if not title or not company:
            return None

        # Parse date
        posted_at = None
        if raw.get("date"):
            try:
                posted_at = datetime.fromisoformat(raw["date"].replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        # Tags contain skills/keywords
        tags = raw.get("tags", []) or []
        description = raw.get("description", "")
        if tags:
            description = f"Tags: {', '.join(tags)}\n\n{description}"

        # Salary
        salary_min = None
        salary_max = None
        if raw.get("salary_min"):
            try:
                salary_min = int(raw["salary_min"])
            except (ValueError, TypeError):
                pass
        if raw.get("salary_max"):
            try:
                salary_max = int(raw["salary_max"])
            except (ValueError, TypeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=job_id,
            url=url,
            title=title,
            company=company,
            location=raw.get("location", "Remote") or "Remote",
            description=description,
            posted_at=posted_at,
            remote_type=RemoteType.WORLDWIDE,  # RemoteOK is explicitly global
            employment_type=raw.get("employment_type", ""),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
        )
