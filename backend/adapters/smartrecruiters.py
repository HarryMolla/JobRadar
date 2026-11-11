"""
SmartRecruiters adapter.
Public API: https://api.smartrecruiters.com/v1/companies/{company}/postings

Companies added in sources_config.yaml or DEFAULT_COMPANIES.
"""
from __future__ import annotations

import logging

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_BASE = "https://api.smartrecruiters.com/v1/companies/{company}/postings"

DEFAULT_COMPANIES = [
    ("IKEA", "IKEA"),
    ("Zalando", "Zalando"),
    ("Delivery-Hero", "Delivery Hero"),
    ("N26-Bank", "N26"),
]


class SmartRecruitersAdapter(BaseAdapter):
    SOURCE_ID = "smartrecruiters"
    DISPLAY_NAME = "SmartRecruiters"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        extra = self.config.get("smartrecruiters_companies", [])
        self._companies = list(DEFAULT_COMPANIES) + [
            (c["slug"], c.get("company", c["slug"])) for c in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for slug, company_name in self._companies:
            try:
                url = API_BASE.format(company=slug)
                data = get_json(url, params={"limit": 100})
                jobs_raw = data.get("content", [])
                self.logger.info("SmartRecruiters %s: %d jobs", company_name, len(jobs_raw))
                for raw in jobs_raw:
                    job = self._normalize(raw, company_name, slug)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("SmartRecruiters %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str, company_slug: str = "") -> JobListing | None:
        job_id = str(raw.get("id", "") or "").strip()
        title = raw.get("name", "")
        if not title:
            return None

        detail_url = raw.get("postingUrl", "") or raw.get("jobUrl", "") or ""
        apply_url = raw.get("applyUrl", "") or ""
        if not detail_url and company_slug and job_id:
            detail_url = f"https://jobs.smartrecruiters.com/{company_slug}/{job_id}"

        location = ""
        loc_data = raw.get("location", {})
        if isinstance(loc_data, dict):
            city = loc_data.get("city", "")
            country = loc_data.get("country", "")
            location = ", ".join(filter(None, [city, country]))
            if loc_data.get("remote"):
                location = f"Remote — {location}".strip(" —")

        remote_type = RemoteType.RESTRICTED if "remote" in location.lower() else RemoteType.UNKNOWN

        rel = raw.get("releasedDate", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(rel, assume_utc_if_naive=True)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"sr_{job_id}",
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company_name,
            location=location,
            description="",
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=raw.get("typeOfEmployment", {}).get("label", ""),
        )
