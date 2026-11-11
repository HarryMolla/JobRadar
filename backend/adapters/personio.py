"""
Personio ATS adapter.
Personio provides a public XML feed for companies using their recruitment platform:
https://{company}.jobs.personio.de/xml or https://{company}.jobs.personio.com/xml

Companies can be configured in sources_config.yaml.
"""
from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from typing import Optional

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

DEFAULT_COMPANIES = [
    ("taxfix", "Taxfix"),
    ("flaschenpost", "Flaschenpost"),
    ("spryker", "Spryker"),
]


class PersonioAdapter(BaseAdapter):
    SOURCE_ID = "personio"
    DISPLAY_NAME = "Personio ATS"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        extra = self.config.get("personio_companies", [])
        self._companies = list(DEFAULT_COMPANIES) + [
            (c["slug"], c.get("company", c["slug"])) for c in extra
        ]

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for slug, company_name in self._companies:
            feed_urls = [
                (f"https://{slug}.jobs.personio.de", f"https://{slug}.jobs.personio.de/xml"),
                (f"https://{slug}.jobs.personio.com", f"https://{slug}.jobs.personio.com/xml"),
            ]
            success = False
            for base_origin, url in feed_urls:
                try:
                    resp = get(url, headers={"Accept": "application/xml, text/xml"})
                    root = ET.fromstring(resp.content)
                    positions = root.findall(".//position")
                    self.logger.info("Personio %s: %d positions found", company_name, len(positions))
                    for pos in positions:
                        job = self._normalize(pos, company_name, slug, base_origin)
                        if job and job.fingerprint not in seen:
                            seen.add(job.fingerprint)
                            all_jobs.append(job)
                    success = True
                    break
                except Exception as exc:
                    self.logger.debug("Personio %s URL %s failed: %s", company_name, url, exc)

            if not success:
                self.logger.warning("Could not fetch Personio feed for %s", company_name)

        return all_jobs

    def _normalize(
        self, pos: ET.Element, company_name: str, slug: str, base_origin: str = ""
    ) -> Optional[JobListing]:
        job_id = (pos.findtext("id", "") or "").strip()
        title = pos.findtext("name", "")
        if not title:
            return None

        # Use explicit feed URL when present, else verified matching host/job/<id>
        origin = base_origin or f"https://{slug}.jobs.personio.de"
        detail_url = (pos.findtext("url", "") or "").strip()
        if not detail_url and job_id:
            detail_url = f"{origin}/job/{job_id}"

        # Location & office
        office = pos.findtext("office", "")
        department = pos.findtext("department", "")
        employment_type = pos.findtext("employmentType", "")

        # Remote status
        remote_type = RemoteType.UNKNOWN
        schedule = (pos.findtext("schedule", "") or "").lower()
        title_lower = title.lower()
        office_lower = office.lower()

        if "remote" in office_lower or "remote" in title_lower or "remote" in schedule:
            remote_type = RemoteType.WORLDWIDE if "worldwide" in (office_lower + title_lower) else RemoteType.RESTRICTED

        # Description from HTML job descriptions
        job_descriptions = pos.findall(".//jobDescription")
        desc_parts = []
        for jd in job_descriptions:
            name = jd.findtext("name", "")
            value = jd.findtext("value", "")
            if value:
                desc_parts.append(f"### {name}\n{value}")
        description = "\n\n".join(desc_parts)

        # Posting date
        created = pos.findtext("createdAt", "")
        posted_at, raw_ts, reliable = parse_utc_timestamp(created)

        return JobListing(
            source=self.SOURCE_ID,
            source_id=f"ps_{job_id}",
            url=detail_url,
            source_job_url=detail_url,
            title=title,
            company=company_name,
            location=office or "Remote",
            description=description[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=employment_type,
        )

