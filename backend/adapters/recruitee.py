"""
Recruitee ATS adapter.
Recruitee provides public APIs for each company subdomain.
API: https://{company}.recruitee.com/api/offers/
"""
from __future__ import annotations

import logging

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_BASE = "https://{company}.recruitee.com/api/offers/"

DEFAULT_COMPANIES = [
    ("basecamp", "Basecamp"),
    ("toggl", "Toggl"),
    ("remote", "Remote.com"),
]


class RecruiteeAdapter(BaseAdapter):
    SOURCE_ID = "recruitee"
    DISPLAY_NAME = "Recruitee ATS"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        extra = self.config.get("recruitee_companies", [])
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
                offers = data.get("offers", data) if isinstance(data, dict) else data
                if not isinstance(offers, list):
                    offers = []
                self.logger.info("Recruitee %s: %d offers", company_name, len(offers))
                for raw in offers:
                    job = self._normalize(raw, company_name)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Recruitee %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        slug = raw.get("slug", job_id)
        url = raw.get("careers_url", f"https://{company_name.lower()}.recruitee.com/o/{slug}/")
        title = raw.get("title", "")
        if not title or not url:
            return None

        location = raw.get("location", "")
        city = raw.get("city", "")
        country = raw.get("country_code", "")
        if city:
            location = f"{city}, {country}".strip(", ")
        is_remote = raw.get("remote", False) or "remote" in (location + title).lower()
        remote_type = RemoteType.WORLDWIDE if is_remote else RemoteType.UNKNOWN

        pub = raw.get("published_at", raw.get("created_at", ""))
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"rt_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description=raw.get("description_plain", raw.get("description", ""))[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=raw.get("employment_type", ""),
        )
