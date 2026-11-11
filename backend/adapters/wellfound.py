"""
Wellfound (formerly AngelList Talent) adapter.
Wellfound does not expose a public API. We use their public GraphQL endpoint
that powers their job board — only public, non-authenticated fields.

NOTE: If Wellfound blocks or rate-limits this adapter, it will log and skip.
Alternative: Use Wellfound job alert emails forwarded to Gmail and parsed.
"""
from __future__ import annotations

import logging

import requests

from backend.adapters.base import BaseAdapter
from backend.core.http_client import DEFAULT_HEADERS
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://wellfound.com/graphql"

QUERY = """
query JobListings($filters: StartupJobFilters!) {
  startupJobs(filters: $filters, first: 50) {
    edges {
      node {
        id
        title
        slug
        remote
        locationNames
        primaryRole { displayName }
        startupRole { compensation }
        startup { name highConcept }
        liveStartDate
        applyUrl
        description
      }
    }
  }
}
"""

ROLE_FILTERS = [
    "Designer",
    "Front End Engineer",
    "Mobile Engineer",
    "Product Designer",
]


class WellfoundAdapter(BaseAdapter):
    SOURCE_ID = "wellfound"
    DISPLAY_NAME = "Wellfound (AngelList)"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for role in ROLE_FILTERS:
            try:
                resp = requests.post(
                    GRAPHQL_URL,
                    json={
                        "query": QUERY,
                        "variables": {
                            "filters": {
                                "role": role,
                                "remote": True,
                            }
                        },
                    },
                    headers={
                        **DEFAULT_HEADERS,
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    timeout=30,
                )
                if resp.status_code != 200:
                    self.logger.warning(
                        "Wellfound returned %d for role %s — skipping",
                        resp.status_code, role
                    )
                    continue
                data = resp.json()
                edges = (
                    data.get("data", {})
                    .get("startupJobs", {})
                    .get("edges", [])
                )
                self.logger.info("Wellfound %s: %d edges", role, len(edges))
                for edge in edges:
                    node = edge.get("node", {})
                    job_id = str(node.get("id", ""))
                    if job_id in seen:
                        continue
                    seen.add(job_id)
                    job = self._normalize(node)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("Wellfound role %s failed: %s", role, exc)

        return all_jobs

    def _normalize(self, node: dict) -> JobListing | None:
        job_id = str(node.get("id", "") or "").strip()
        slug = str(node.get("slug", "") or "").strip()
        apply_url = node.get("applyUrl", "") or ""
        detail_url = f"https://wellfound.com/jobs/{slug}" if slug else ""
        title = node.get("title", "")
        startup = node.get("startup", {}) or {}
        company = startup.get("name", "")
        if not title or not company:
            return None

        locations = node.get("locationNames", []) or []
        location = ", ".join(locations) if locations else "Remote"
        is_remote = node.get("remote", False)
        remote_type = RemoteType.WORLDWIDE if is_remote else RemoteType.RESTRICTED

        live_start = node.get("liveStartDate", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(live_start)

        description = node.get("description", "") or startup.get("highConcept", "")

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"wf_{job_id}",
            url=apply_url or detail_url,
            source_job_url=detail_url,
            apply_url=apply_url,
            title=title,
            company=company,
            location=location,
            description=description[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
        )
