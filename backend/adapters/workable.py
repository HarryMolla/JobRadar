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

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

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
        shortcode = str(raw.get("shortcode", "") or "").strip()
        job_id = shortcode or str(raw.get("id", "") or "").strip()
        title = raw.get("title", "")
        if not title:
            return None

        detail_url = raw.get("url", "") or (
            f"https://apply.workable.com/{slug}/j/{shortcode}/" if slug and shortcode else ""
        )
        apply_url = raw.get("application_url", "") or raw.get("apply_url", "") or ""

        location = raw.get("location", {})
        if isinstance(location, dict):
            city = location.get("city", "")
            country = location.get("country", "")
            location_str = ", ".join(filter(None, [city, country]))
        else:
            location_str = str(location) if location else ""

        is_remote = raw.get("remote", False)
        remote_type = RemoteType.RESTRICTED if is_remote else RemoteType.UNKNOWN

        pub = raw.get("published_on", raw.get("created_at", ""))
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub, assume_utc_if_naive=False)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"wb_{job_id}",
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company_name,
            location=location_str,
            description=raw.get("description", "")[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=raw.get("employment_type", ""),
        )
