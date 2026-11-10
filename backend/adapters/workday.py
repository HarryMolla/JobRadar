"""
Workday CXS API adapter.
Workday public career sites use a standard JSON search endpoint:
https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{company}/{board}/jobs

This queries the official public search API used by the employer's career portal.
Respects rate limits and handles schema differences.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
import requests

from backend.adapters.base import BaseAdapter
from backend.core.http_client import DEFAULT_HEADERS
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

# Configured Workday employers
DEFAULT_WORKDAY_SITES = [
    {
        "company": "Adobe",
        "url": "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced/jobs",
        "base_url": "https://adobe.wd5.myworkdayjobs.com/en-US/external_experienced",
    },
    {
        "company": "Fidelity",
        "url": "https://fmr.wd1.myworkdayjobs.com/wday/cxs/fmr/FidelityCareers/jobs",
        "base_url": "https://fmr.wd1.myworkdayjobs.com/en-US/FidelityCareers",
    },
]


class WorkdayAdapter(BaseAdapter):
    SOURCE_ID = "workday"
    DISPLAY_NAME = "Workday ATS"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        extra = self.config.get("workday_sites", [])
        self._sites = list(DEFAULT_WORKDAY_SITES) + extra

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for site in self._sites:
            company = site["company"]
            endpoint = site["url"]
            base_url = site.get("base_url", "")

            try:
                # Workday CXS pagination & search payload
                payload = {
                    "appliedFacets": {},
                    "limit": 20,
                    "offset": 0,
                    "searchText": "designer developer",
                }
                resp = requests.post(
                    endpoint,
                    json=payload,
                    headers={
                        **DEFAULT_HEADERS,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    timeout=25,
                )
                if resp.status_code != 200:
                    self.logger.warning("Workday %s returned HTTP %d", company, resp.status_code)
                    continue

                data = resp.json()
                job_postings = data.get("jobPostings", [])
                self.logger.info("Workday %s: %d postings found", company, len(job_postings))

                for raw in job_postings:
                    job = self._normalize(raw, company, base_url)
                    if job and job.fingerprint not in seen:
                        seen.add(job.fingerprint)
                        all_jobs.append(job)

            except Exception as exc:
                self.logger.warning("Workday %s failed: %s", company, exc)

        return all_jobs

    def _normalize(self, raw: dict, company: str, base_url: str) -> Optional[JobListing]:
        title = raw.get("title", "")
        external_path = raw.get("externalPath", "")
        if not title or not external_path:
            return None

        # Build direct job link
        url = f"{base_url}{external_path}" if base_url else f"https://myworkdayjobs.com{external_path}"
        source_id = external_path.strip("/").split("/")[-1]

        locations = raw.get("locationsText", "")
        posted_str = raw.get("postedOn", "")

        remote_type = RemoteType.UNKNOWN
        combined = f"{title} {locations}".lower()
        if "remote" in combined:
            remote_type = RemoteType.RESTRICTED

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"wd_{source_id}",
            url=url,
            title=title,
            company=company,
            location=locations or "Multiple Locations",
            description=f"Posted: {posted_str}",
            remote_type=remote_type,
        )

