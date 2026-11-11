"""
Jobicy adapter.
Public API: https://jobicy.com/api/v2/remote-jobs
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_URL = "https://jobicy.com/api/v2/remote-jobs"


class JobicyAdapter(BaseAdapter):
    SOURCE_ID = "jobicy"
    DISPLAY_NAME = "Jobicy"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        params = {"count": 50, "geo": "worldwide", "industry": "design"}
        all_jobs = []
        seen: set[str] = set()

        # Fetch design + dev categories
        for industry in ["design", "engineering"]:
            try:
                data = get_json(API_URL, params={"count": 50, "industry": industry})
                raw_jobs = data.get("jobs", [])
                self.logger.info("Jobicy %s: %d raw", industry, len(raw_jobs))
                for raw in raw_jobs:
                    jid = str(raw.get("id", raw.get("jobSlug", "")))
                    if jid in seen:
                        continue
                    seen.add(jid)
                    job = self._normalize(raw)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Jobicy %s failed: %s", industry, exc)

        return all_jobs

    def _normalize(self, raw: dict) -> JobListing | None:
        job_id = str(raw.get("id", raw.get("jobSlug", "")))
        detail_url = raw.get("url", "") or ""
        apply_url = raw.get("applyUrl", "") or raw.get("applicationUrl", "") or ""
        title = raw.get("jobTitle", "")
        company = raw.get("companyName", "")
        if not title:
            return None

        pub = raw.get("pubDate", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub, assume_utc_if_naive=True)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=job_id,
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company,
            location=raw.get("jobGeo", "Remote") or "Remote",
            description=raw.get("jobDescription", ""),
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,
            employment_type=raw.get("jobType", ""),
            salary_min=raw.get("annualSalaryMin"),
            salary_max=raw.get("annualSalaryMax"),
            salary_currency=raw.get("salaryCurrency", "USD"),
        )
