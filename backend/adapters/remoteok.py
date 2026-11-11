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
from backend.core.time_utils import parse_utc_timestamp

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
        detail_url = raw.get("url", "") or ""
        apply_url = raw.get("apply_url", "") or ""
        title = raw.get("position", "")
        company = raw.get("company", "")
        if not title or not company:
            return None

        # Parse original posting date in UTC
        raw_date = raw.get("date") or raw.get("epoch")
        posted_at, raw_ts, reliable = parse_utc_timestamp(raw_date, assume_utc_if_naive=True)

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
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company,
            location=raw.get("location", "Remote") or "Remote",
            description=description,
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,  # RemoteOK is explicitly global
            employment_type=raw.get("employment_type", ""),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
        )
