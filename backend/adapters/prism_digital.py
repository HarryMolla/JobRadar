"""
Prism Digital (Dubai, UAE) careers adapter.
Reads structured Next.js __NEXT_DATA__ from https://www.prism-me.com/careers
and detail pages /careers/{slug}, distinguishing original createdAt from updatedAt.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional

from bs4 import BeautifulSoup

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

CAREERS_URL = "https://www.prism-me.com/careers"
DETAIL_URL = "https://www.prism-me.com/careers/{slug}"
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL)


class PrismDigitalAdapter(BaseAdapter):
    SOURCE_ID = "prism_digital"
    DISPLAY_NAME = "Prism Digital"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._max_pages = int(self.config.get("prism_max_pages", 2))
        self._max_details = int(self.config.get("prism_max_details", 12))

    def fetch(self) -> list[JobListing]:
        now_utc = datetime.now(timezone.utc)
        items: list[dict] = []
        seen_slugs: set[str] = set()

        for page in range(1, self._max_pages + 1):
            params = {"page": page} if page > 1 else None
            resp = get(CAREERS_URL, params=params, timeout=25, check_robots=True, use_cache=True)
            page_props = self._extract_page_props(resp.text)
            careers = page_props.get("initialCareers") or []
            if not isinstance(careers, list) or not careers:
                break
            for item in careers:
                slug = (item.get("slug") or "").strip()
                if slug and slug not in seen_slugs:
                    seen_slugs.add(slug)
                    items.append(item)
            total_pages = int(page_props.get("initialTotalPages") or 1)
            if page >= total_pages:
                break

        jobs: list[JobListing] = []
        for item in items[: self._max_details]:
            slug = (item.get("slug") or "").strip()
            if not slug:
                continue
            detail_url = DETAIL_URL.format(slug=slug)
            detail = self._fetch_detail_props(detail_url)
            job = self._normalize(item, detail, detail_url, now_utc)
            if job:
                jobs.append(job)

        return jobs

    def _extract_page_props(self, html_text: str) -> dict:
        m = _NEXT_DATA_RE.search(html_text)
        if not m:
            return {}
        try:
            data = json.loads(m.group(1))
            return data.get("props", {}).get("pageProps", {}) or {}
        except Exception as exc:
            self.logger.debug("Prism __NEXT_DATA__ parse failed: %s", exc)
            return {}

    def _fetch_detail_props(self, url: str) -> dict:
        try:
            resp = get(url, timeout=20, check_robots=True, use_cache=True)
            props = self._extract_page_props(resp.text)
            for key in ("career", "job", "careerDetails", "data"):
                val = props.get(key)
                if isinstance(val, dict) and ("createdAt" in val or "position" in val or "title" in val):
                    return val
            return props
        except Exception as exc:
            self.logger.warning("Prism detail fetch failed for %s: %s", url, exc)
            return {}

    def _normalize(
        self, summary: dict, detail: dict, url: str, now_utc: datetime
    ) -> Optional[JobListing]:
        title = (detail.get("position") or detail.get("title") or summary.get("position") or "").strip()
        if not title:
            return None

        job_id = str(detail.get("_id") or summary.get("_id") or summary.get("slug") or "")
        location_raw = (detail.get("location") or summary.get("location") or "Dubai").strip()
        location = f"{location_raw}, UAE" if "uae" not in location_raw.lower() and "remote" not in location_raw.lower() else location_raw
        work_loc_type = (detail.get("workLocationType") or summary.get("workLocationType") or "").lower()

        # Strictly use original createdAt for posted_at; keep updatedAt separate
        created_raw = detail.get("createdAt") or detail.get("publishedAt") or summary.get("createdAt")
        updated_raw = detail.get("updatedAt") or summary.get("updatedAt")
        posted_at, raw_ts, reliable = parse_utc_timestamp(created_raw)
        updated_at, upd_raw, _ = parse_utc_timestamp(updated_raw)
        if not raw_ts and upd_raw:
            raw_ts = upd_raw

        desc_raw = (
            detail.get("description")
            or detail.get("jobDescription")
            or detail.get("overview")
            or ""
        )
        description = BeautifulSoup(str(desc_raw), "html.parser").get_text(" ", strip=True)

        remote_type = RemoteType.ONSITE
        if "remote" in work_loc_type or "remote" in title.lower():
            remote_type = (
                RemoteType.WORLDWIDE
                if "worldwide" in description.lower() or "anywhere" in description.lower()
                else RemoteType.RESTRICTED
            )
        elif "hybrid" in work_loc_type:
            remote_type = RemoteType.HYBRID

        return JobListing(
            source=self.SOURCE_ID,
            source_name=self.DISPLAY_NAME,
            source_id=f"pr_{job_id}",
            url=url,
            source_job_url=url,
            title=title,
            company="Prism Digital",
            location=location,
            work_location=location,
            description=description[:5000],
            posted_at=posted_at,
            updated_at=updated_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            last_checked_at=now_utc,
            remote_type=remote_type,
            employment_type=str(detail.get("jobType") or summary.get("jobType") or ""),
        )

