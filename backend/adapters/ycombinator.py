"""
Y Combinator Work at a Startup adapter.
Fetches from https://www.workatastartup.com/jobs using their public API.
Note: This endpoint may require session cookies. We attempt the request and
skip gracefully if blocked.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

# YC Work at a Startup has a public search API
API_URL = "https://www.workatastartup.com/companies/fetch-jobs"


class YCombinatorAdapter(BaseAdapter):
    SOURCE_ID = "ycombinator"
    DISPLAY_NAME = "Y Combinator (Work at a Startup)"
    ENABLED = True

    # Role types relevant to our search
    ROLES = ["Design", "Frontend", "Full Stack"]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for role in self.ROLES:
            try:
                # Public endpoint parameters
                data = get_json(
                    API_URL,
                    params={
                        "job_type": role,
                        "remote": "true",
                        "limit": 50,
                    },
                    headers={
                        "Accept": "application/json",
                        "Referer": "https://www.workatastartup.com/jobs",
                    },
                )
                jobs_raw = data if isinstance(data, list) else data.get("jobs", [])
                self.logger.info("YC %s: %d jobs", role, len(jobs_raw))
                for raw in jobs_raw:
                    jid = str(raw.get("id", ""))
                    if jid in seen:
                        continue
                    seen.add(jid)
                    job = self._normalize(raw)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.warning("YC role %s failed (may need auth): %s", role, exc)

        return all_jobs

    def _normalize(self, raw: dict) -> JobListing | None:
        job_id = str(raw.get("id", ""))
        title = raw.get("title", raw.get("role", ""))
        company = raw.get("company", {})
        company_name = company.get("name", "") if isinstance(company, dict) else str(company)
        url = raw.get("url", f"https://www.workatastartup.com/jobs/{job_id}")

        if not title:
            return None

        location = raw.get("location", "")
        is_remote = raw.get("remote", False) or "remote" in location.lower()
        remote_type = RemoteType.WORLDWIDE if is_remote else RemoteType.UNKNOWN

        posted_at = None
        created = raw.get("created_at", raw.get("posted_at", ""))
        if created:
            try:
                posted_at = datetime.fromisoformat(created.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"yc_{job_id}",
            url=url,
            title=title,
            company=company_name,
            location=location,
            description=raw.get("description", "")[:5000],
            posted_at=posted_at,
            remote_type=remote_type,
        )
