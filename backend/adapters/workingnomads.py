"""
Working Nomads adapter.
Public API: https://www.workingnomads.com/api/exposed_jobs/
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_URL = "https://www.workingnomads.com/api/exposed_jobs/"

# Category tags to filter
CATEGORIES = ["design", "front-end", "javascript"]


class WorkingNomadsAdapter(BaseAdapter):
    SOURCE_ID = "workingnomads"
    DISPLAY_NAME = "Working Nomads"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for category in CATEGORIES:
            try:
                data = get_json(API_URL, params={"category": category})
                raw_jobs = data if isinstance(data, list) else data.get("results", [])
                self.logger.info("WorkingNomads %s: %d raw", category, len(raw_jobs))
                for raw in raw_jobs:
                    jid = str(raw.get("id", ""))
                    if jid in seen:
                        continue
                    seen.add(jid)
                    job = self._normalize(raw)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("WorkingNomads %s failed: %s", category, exc)

        return all_jobs

    def _normalize(self, raw: dict) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        detail_url = raw.get("url", "") or ""
        apply_url = raw.get("apply_url", "") or ""
        title = raw.get("title", "")
        company = raw.get("company", "") or raw.get("company_name", "")
        if not title:
            return None

        pub = raw.get("pub_date") or raw.get("created", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub, assume_utc_if_naive=True)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=job_id,
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company,
            location=raw.get("location", "Remote") or "Remote",
            description=raw.get("description", ""),
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,
        )
