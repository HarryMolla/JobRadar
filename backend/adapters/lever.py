"""
Lever ATS adapter.
Lever provides a public JSON API for each company.
API: https://api.lever.co/v0/postings/{company}?mode=json

Companies configured in sources_config.yaml or DEFAULT_COMPANIES.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

API_BASE = "https://api.lever.co/v0/postings/{company}?mode=json&limit=100"

DEFAULT_COMPANIES = [
    ("netflix", "Netflix"),
    ("cloudflare", "Cloudflare"),
    ("stripe", "Stripe"),
    ("plaid", "Plaid"),
    ("brex", "Brex"),
    ("mercury", "Mercury"),
    ("carta", "Carta"),
    ("rippling", "Rippling"),
    ("scale", "Scale AI"),
    ("dbt-labs", "dbt Labs"),
]


class LeverAdapter(BaseAdapter):
    SOURCE_ID = "lever"
    DISPLAY_NAME = "Lever ATS"
    ENABLED = True

    def __init__(self, config: dict | None = None):
        super().__init__(config)
        extra = self.config.get("lever_companies", [])
        self._companies = list(DEFAULT_COMPANIES) + [
            (c["slug"], c.get("company", c["slug"])) for c in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for slug, company_name in self._companies:
            try:
                url = API_BASE.format(company=slug)
                postings = get_json(url)
                if not isinstance(postings, list):
                    postings = postings.get("data", [])
                self.logger.info("Lever %s: %d postings", company_name, len(postings))
                for raw in postings:
                    job = self._normalize(raw, company_name)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Lever %s failed: %s", company_name, exc)

        return all_jobs

    def _normalize(self, raw: dict, company_name: str) -> JobListing | None:
        job_id = raw.get("id", "")
        url = raw.get("hostedUrl", raw.get("applyUrl", ""))
        title = raw.get("text", "")
        if not title or not url:
            return None

        location = ""
        categories = raw.get("categories", {})
        if isinstance(categories, dict):
            location = categories.get("location", "")

        commitment = categories.get("commitment", "") if isinstance(categories, dict) else ""

        # Remote detection
        remote_type = RemoteType.UNKNOWN
        location_lower = (location + " " + title).lower()
        if "remote" in location_lower:
            remote_type = RemoteType.RESTRICTED

        # Description
        lists = raw.get("lists", [])
        desc_parts = []
        for section in lists:
            if isinstance(section, dict):
                desc_parts.append(section.get("text", ""))
                for item in section.get("content", "").split("<br>"):
                    desc_parts.append(item.strip())
        description = " ".join(filter(None, desc_parts))

        # Date
        posted_at = None
        created = raw.get("createdAt")
        if created:
            try:
                posted_at = datetime.fromtimestamp(created / 1000, tz=timezone.utc)
            except (ValueError, TypeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"lv_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description=description[:5000],
            posted_at=posted_at,
            remote_type=remote_type,
            employment_type=commitment,
        )
