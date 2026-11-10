"""
Workable adapter.
Workable provides public job listing pages.
We use their public subdomain API pattern:
https://{company}.workable.com/api/v3/accounts/{account}/jobs

For companies where this endpoint is public, we query it.
Otherwise we use the shared Workable job board search.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

SHARED_BOARD_URL = "https://apply.workable.com/api/v3/accounts/{slug}/jobs"

DEFAULT_COMPANIES = [
    ("typeform", "Typeform"),
    ("hotjar", "Hotjar"),
    ("doist", "Doist"),
]


class WorkableAdapter(BaseAdapter):
    SOURCE_ID = "workable"
    DISPLAY_NAME = "Workable ATS"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        extra = self.config.get("workable_companies", [])
        self._companies = list(DEFAULT_COMPANIES) + [
            (c["slug"], c.get("company", c["slug"])) for c in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for slug, company_name in self._companies:
            try:
                url = SHARED_BOARD_URL.format(slug=slug)
                data = get_json(
                    url,
                    params={"details": "true", "limit": 100},
                    headers={"Accept": "application/json"},
                )
                jobs_raw = data.get("results", [])
                self.logger.info("Workable %s: %d jobs", company_name, len(jobs_raw))
                for raw in jobs_raw:
                    job = self._normalize(raw, company_name, slug)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Workable %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str, slug: str) -> JobListing | None:
        job_id = raw.get("shortcode", raw.get("id", ""))
        title = raw.get("title", "")
        if not title:
            return None

        url = f"https://apply.workable.com/{slug}/j/{job_id}/"

        location = raw.get("location", {})
        if isinstance(location, dict):
            city = location.get("city", "")
            country = location.get("country", "")
            location_str = ", ".join(filter(None, [city, country]))
        else:
            location_str = str(location) if location else ""

        is_remote = raw.get("remote", False)
        remote_type = RemoteType.RESTRICTED if is_remote else RemoteType.UNKNOWN

        posted_at = None
        pub = raw.get("published_on", raw.get("created_at", ""))
        if pub:
            try:
                posted_at = datetime.fromisoformat(pub.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"wb_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location_str,
            description=raw.get("description", "")[:5000],
            posted_at=posted_at,
            remote_type=remote_type,
            employment_type=raw.get("employment_type", ""),
        )
