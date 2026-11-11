"""
Hays UAE specialist recruitment agency adapter.
Parses permitted /job-search listings and Schema.org JobPosting JSON-LD detail pages.
Date-only datePosted strings (e.g. '2026-11-10') are marked timestamp_reliable=False
so the central 24h age filter excludes ambiguous postings rather than guessing time-of-day.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.hays.ae/job-search"
_JOB_DETAIL_RE = re.compile(r"/job-detail/[^\"'\s<>?#]+", re.IGNORECASE)


class HaysUAEAdapter(BaseAdapter):
    SOURCE_ID = "hays_uae"
    DISPLAY_NAME = "Hays UAE"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._max_details = int(self.config.get("hays_max_details", 10))

    def fetch(self) -> list[JobListing]:
        now_utc = datetime.now(timezone.utc)
        resp = get(SEARCH_URL, timeout=25, check_robots=True, use_cache=True)
        detail_paths: list[str] = []
        seen: set[str] = set()
        for match in _JOB_DETAIL_RE.findall(resp.text):
            clean = match.split("&")[0].rstrip("/")
            full_url = urljoin("https://www.hays.ae", clean)
            if full_url not in seen:
                seen.add(full_url)
                detail_paths.append(full_url)
            if len(detail_paths) >= self._max_details:
                break

        jobs: list[JobListing] = []
        for url in detail_paths:
            job = self._fetch_and_normalize(url, now_utc)
            if job:
                jobs.append(job)

        return jobs

    def _fetch_and_normalize(self, url: str, now_utc: datetime) -> Optional[JobListing]:
        try:
            resp = get(url, timeout=20, check_robots=True, use_cache=True)
        except Exception as exc:
            self.logger.warning("Hays detail fetch failed for %s: %s", url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        ld = self._extract_jobposting_ld(soup)
        if not ld:
            return None

        title = (ld.get("title") or "").strip()
        if not title:
            return None

        org = ld.get("hiringOrganization") or {}
        company = (org.get("name") if isinstance(org, dict) else str(org)) or "Hays UAE Client"
        location = self._extract_location(ld) or "UAE"
        desc_html = ld.get("description") or ""
        description = BeautifulSoup(str(desc_html), "html.parser").get_text(" ", strip=True)

        posted_at, raw_ts, reliable = parse_utc_timestamp(ld.get("datePosted"))
        slug = url.rstrip("/").split("/")[-1]
        remote_type = RemoteType.UNKNOWN
        if "remote" in f"{title} {location} {description}".lower():
            remote_type = RemoteType.RESTRICTED

        apply_url = str(
            ld.get("applicationUrl")
            or ld.get("applyUrl")
            or (ld.get("url") if ld.get("url") and ld.get("url") != url else "")
            or ""
        ).strip()

        return JobListing(
            source=self.SOURCE_ID,
            source_name=self.DISPLAY_NAME,
            source_id=f"hy_{slug[:64]}",
            url=apply_url or url,
            source_job_url=url,
            apply_url=apply_url,
            title=title,
            company=company.strip(),
            location=location,
            work_location=location,
            description=description[:5000],
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            last_checked_at=now_utc,
            remote_type=remote_type,
            employment_type=str(ld.get("employmentType") or ""),
        )

    def _extract_jobposting_ld(self, soup: BeautifulSoup) -> Optional[dict]:
        for tag in soup.find_all("script", type="application/ld+json"):
            raw = (tag.string or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except Exception:
                continue
            candidates = (
                data.get("@graph", [data])
                if isinstance(data, dict)
                else (data if isinstance(data, list) else [])
            )
            for item in candidates:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return item
        return None

    def _extract_location(self, ld: dict) -> str:
        loc = ld.get("jobLocation")
        if isinstance(loc, list) and loc:
            loc = loc[0]
        if isinstance(loc, dict):
            addr = loc.get("address", {})
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                    addr.get("addressCountry", ""),
                ]
                return ", ".join(p for p in parts if p)
        return ""

