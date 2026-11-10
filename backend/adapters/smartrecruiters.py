"""
SmartRecruiters adapter.
Public API: https://api.smartrecruiters.com/v1/companies/{company}/postings

Companies added in sources_config.yaml or DEFAULT_COMPANIES.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType

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
                    job = self._normalize(raw, company_name)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("SmartRecruiters %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str) -> JobListing | None:
        job_id = raw.get("id", "")
        ref_num = raw.get("refNumber", job_id)
        title = raw.get("name", "")
        if not title:
            return None

        url = f"https://jobs.smartrecruiters.com/{company_name.replace(' ','-')}/{ref_num}"

        location = ""
        loc_data = raw.get("location", {})
        if isinstance(loc_data, dict):
            city = loc_data.get("city", "")
            country = loc_data.get("country", "")
            location = ", ".join(filter(None, [city, country]))
            if loc_data.get("remote"):
                location = f"Remote — {location}".strip(" —")

        remote_type = RemoteType.RESTRICTED if "remote" in location.lower() else RemoteType.UNKNOWN

        posted_at = None
        rel = raw.get("releasedDate", "")
        if rel:
            try:
                posted_at = datetime.fromisoformat(rel.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"sr_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description="",
            posted_at=posted_at,
            remote_type=remote_type,
            employment_type=raw.get("typeOfEmployment", {}).get("label", ""),
        )
