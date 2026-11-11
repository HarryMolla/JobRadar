"""
Ashby ATS adapter.
Ashby provides public JSON APIs for each company.
API: https://api.ashbyhq.com/posting-api/job-board/{company}
"""
from __future__ import annotations

import logging

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_BASE = "https://api.ashbyhq.com/posting-api/job-board/{company}"

DEFAULT_COMPANIES = [
    ("linear", "Linear"),
    ("loom", "Loom"),
    ("ramp", "Ramp"),
    ("mercury", "Mercury"),
    ("dbt-labs", "dbt Labs"),
    ("watershed", "Watershed"),
    ("anyscale", "Anyscale"),
]


class AshbyAdapter(BaseAdapter):
    SOURCE_ID = "ashby"
    DISPLAY_NAME = "Ashby ATS"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        extra = self.config.get("ashby_companies", [])
        self._companies = list(DEFAULT_COMPANIES) + [
            (c["slug"], c.get("company", c["slug"])) for c in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for slug, company_name in self._companies:
            try:
                url = API_BASE.format(company=slug)
                data = get_json(url)
                jobs_raw = data.get("jobs", [])
                self.logger.info("Ashby %s: %d jobs", company_name, len(jobs_raw))
                for raw in jobs_raw:
                    job = self._normalize(raw, company_name)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Ashby %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str) -> JobListing | None:
        job_id = raw.get("id", "")
        url = raw.get("jobUrl", "")
        title = raw.get("title", "")
        if not title or not url:
            return None

        location = raw.get("location", "")
        is_remote = raw.get("isRemote", False)
        remote_type = RemoteType.WORLDWIDE if is_remote else RemoteType.UNKNOWN

        employment_type = raw.get("employmentType", "")

        # Sections contain description
        sections = raw.get("descriptionSections", [])
        desc_parts = [s.get("descriptionHtml", "") or s.get("description", "") for s in sections]
        description = "\n\n".join(filter(None, desc_parts))

        pub = raw.get("publishedDate", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub, assume_utc_if_naive=True)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"ab_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description=description[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=employment_type,
        )
