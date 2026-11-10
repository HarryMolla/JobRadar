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
        url = raw.get("url", "") or raw.get("apply_url", "")
        title = raw.get("title", "")
        company = raw.get("company", "") or raw.get("company_name", "")
        if not title or not url:
            return None

        posted_at = None
        pub = raw.get("pub_date", raw.get("created", ""))
        if pub:
            try:
                posted_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=job_id,
            url=url,
            title=title,
            company=company,
            location=raw.get("location", "Remote") or "Remote",
            description=raw.get("description", ""),
            posted_at=posted_at,
            remote_type=RemoteType.WORLDWIDE,
        )
