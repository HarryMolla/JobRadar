"""
Greenhouse ATS adapter.
Greenhouse provides a public JSON API for each company board.
API: https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs

This adapter reads a configured list of board tokens.
Companies must be added to sources_config.yaml.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

# Default Greenhouse company boards to monitor
# Format: (board_token, company_display_name)
# Add more via sources_config.yaml
DEFAULT_BOARDS = [
    ("figma", "Figma"),
    ("notion", "Notion"),
    ("linear", "Linear"),
    ("vercel", "Vercel"),
    ("retool", "Retool"),
    ("airtable", "Airtable"),
    ("miro", "Miro"),
    ("loom", "Loom"),
    ("descript", "Descript"),
    ("pitch", "Pitch"),
]


class GreenhouseAdapter(BaseAdapter):
    SOURCE_ID = "greenhouse"
    DISPLAY_NAME = "Greenhouse ATS"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        # Merge default boards with any configured in sources_config.yaml
        extra = self.config.get("greenhouse_boards", [])
        self._boards = list(DEFAULT_BOARDS) + [
            (b["token"], b.get("company", b["token"])) for b in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for token, company_name in self._boards:
            try:
                url = API_BASE.format(token=token)
                data = get_json(url)
                jobs_raw = data.get("jobs", [])
                self.logger.info("Greenhouse %s: %d jobs", company_name, len(jobs_raw))
                for raw in jobs_raw:
                    job = self._normalize(raw, company_name)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Greenhouse %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        url = raw.get("absolute_url", "")
        title = raw.get("title", "")
        if not title or not url:
            return None

        # Location
        offices = raw.get("offices", [])
        location = offices[0].get("name", "") if offices else ""
        if not location:
            location_data = raw.get("location", {})
            location = location_data.get("name", "") if isinstance(location_data, dict) else ""

        # Remote detection from title + location
        remote_type = RemoteType.UNKNOWN
        location_lower = location.lower()
        title_lower = title.lower()
        if "remote" in location_lower or "remote" in title_lower:
            remote_type = RemoteType.RESTRICTED  # Greenhouse jobs may be US-focused remote

        # Department
        departments = raw.get("departments", [])
        dept = departments[0].get("name", "") if departments else ""

        # Content / description
        content = raw.get("content", "") or ""

        # Original posting date vs last-updated date (never treat updated_at as posted_at)
        first_pub = raw.get("first_published")
        updated_raw = raw.get("updated_at")
        posted_at, raw_ts, reliable = parse_utc_timestamp(first_pub)
        updated_at, updated_ts, _ = parse_utc_timestamp(updated_raw)
        if not raw_ts and updated_ts:
            raw_ts = f"updated_at:{updated_ts}"

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"gh_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description=f"Department: {dept}\n\n{content}"[:5000],
            posted_at=posted_at,
            updated_at=updated_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
        )
