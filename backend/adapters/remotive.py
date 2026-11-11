"""
Remotive adapter.
Public API: https://remotive.com/api/remote-jobs
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import urlencode

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

API_BASE = "https://remotive.com/api/remote-jobs"

# Categories to fetch
CATEGORIES = [
    "design",
    "software-dev",
]


class RemotiveAdapter(BaseAdapter):
    SOURCE_ID = "remotive"
    DISPLAY_NAME = "Remotive"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen_ids: set[str] = set()

        for category in CATEGORIES:
            try:
                url = f"{API_BASE}?category={category}&limit=100"
                data = get_json(url)
                raw_jobs = data.get("jobs", [])
                self.logger.info("Remotive %s: %d raw jobs", category, len(raw_jobs))
                for raw in raw_jobs:
                    jid = str(raw.get("id", ""))
                    if jid in seen_ids:
                        continue
                    seen_ids.add(jid)
                    job = self._normalize(raw)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Remotive category %s failed: %s", category, exc)

        return all_jobs

    def _normalize(self, raw: dict) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        url = raw.get("url", "")
        title = raw.get("title", "")
        company = raw.get("company_name", "")
        if not title or not url:
            return None

        pub = raw.get("publication_date", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(pub, assume_utc_if_naive=True)

        tags = raw.get("tags", []) or []
        description = raw.get("description", "")
        if tags:
            description = f"Tags: {', '.join(tags)}\n\n{description}"

        # Salary string parsing
        salary_str = raw.get("salary", "") or ""
        salary_min, salary_max = _parse_salary_range(salary_str)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=job_id,
            url=url,
            title=title,
            company=company,
            location=raw.get("candidate_required_location", "Remote") or "Remote",
            description=description,
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,  # Remotive is global-focused
            employment_type=raw.get("job_type", ""),
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency="USD",
        )


def _parse_salary_range(salary_str: str) -> tuple[int | None, int | None]:
    """Try to parse salary ranges like '$60,000 - $80,000' or '60k-80k'."""
    import re
    if not salary_str:
        return None, None
    nums = re.findall(r"[\d,]+", salary_str.replace("k", "000"))
    parsed = []
    for n in nums:
        try:
            parsed.append(int(n.replace(",", "")))
        except ValueError:
            pass
    if len(parsed) >= 2:
        return min(parsed[:2]), max(parsed[:2])
    if len(parsed) == 1:
        return parsed[0], None
    return None, None
