"""
SawaTech (UAE) careers adapter.
Uses SawaTech's public WordPress RSS feed (https://www.sawatech.com/jobs/feed/)
and Schema.org JobPosting JSON-LD metadata on detail pages when within the age window.
"""
from __future__ import annotations

import html
import json
import logging
import re
from calendar import timegm
from datetime import datetime, timezone
from typing import Optional

import feedparser
from bs4 import BeautifulSoup

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

FEED_URL = "https://www.sawatech.com/jobs/feed/"


class SawaTechAdapter(BaseAdapter):
    SOURCE_ID = "sawatech"
    DISPLAY_NAME = "SawaTech"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._max_detail_fetches = int(self.config.get("sawatech_max_details", 10))

    def fetch(self) -> list[JobListing]:
        resp = get(FEED_URL, timeout=25, check_robots=True, use_cache=True)
        feed = feedparser.parse(resp.content)
        if getattr(feed, "bozo", False) and not getattr(feed, "entries", None):
            raise RuntimeError(f"SawaTech RSS parse failed: {feed.bozo_exception}")

        jobs: list[JobListing] = []
        seen: set[str] = set()
        now_utc = datetime.now(timezone.utc)
        detail_fetches = 0

        for entry in getattr(feed, "entries", []):
            url = (entry.get("link") or "").strip()
            title = (entry.get("title") or "").strip()
            if not url or not title or url in seen:
                continue
            seen.add(url)

            raw_pub = entry.get("published", "")
            posted_at, raw_ts, reliable = parse_utc_timestamp(raw_pub)
            if posted_at is None:
                parsed_struct = getattr(entry, "published_parsed", None) or entry.get("published_parsed")
                if parsed_struct:
                    try:
                        posted_at = datetime.fromtimestamp(timegm(parsed_struct), tz=timezone.utc)
                        raw_ts = raw_ts or posted_at.isoformat()
                        reliable = True
                    except Exception:
                        pass

            summary_html = entry.get("summary", "") or ""
            description = BeautifulSoup(summary_html, "html.parser").get_text(" ", strip=True)
            location = "Dubai, UAE" if "dubai" in (title + " " + url).lower() else "UAE"
            employment_type = ""

            # Only fetch detail JSON-LD if RSS timestamp is plausibly recent (saves Actions bandwidth)
            is_potentially_fresh = (
                posted_at is not None
                and reliable
                and 0 <= (now_utc - posted_at).total_seconds() <= 48 * 3600
            )
            if is_potentially_fresh and detail_fetches < self._max_detail_fetches:
                detail_fetches += 1
                detail = self._fetch_detail_jsonld(url)
                if detail:
                    ld_date, ld_raw, ld_rel = parse_utc_timestamp(detail.get("datePosted"))
                    if ld_date and ld_rel:
                        posted_at, raw_ts, reliable = ld_date, ld_raw, ld_rel
                    if detail.get("description"):
                        description = BeautifulSoup(
                            html.unescape(detail["description"]), "html.parser"
                        ).get_text(" ", strip=True)
                    loc_text = self._extract_ld_location(detail)
                    if loc_text:
                        location = loc_text
                    emp = detail.get("employmentType", "")
                    if isinstance(emp, list):
                        employment_type = ", ".join(str(x) for x in emp)
                    elif emp:
                        employment_type = str(emp)

            slug = url.rstrip("/").split("/")[-1]
            combined_lower = f"{title} {location} {description}".lower()
            remote_type = RemoteType.ONSITE
            if "remote" in combined_lower:
                remote_type = (
                    RemoteType.WORLDWIDE
                    if "worldwide" in combined_lower or "anywhere" in combined_lower
                    else RemoteType.RESTRICTED
                )
            elif "hybrid" in combined_lower:
                remote_type = RemoteType.HYBRID

            jobs.append(
                JobListing(
                    source=self.SOURCE_ID,
                    source_name=self.DISPLAY_NAME,
                    source_id=f"sw_{slug[:64]}",
                    url=url,
                    source_job_url=url,
                    title=title,
                    company="SawaTech",
                    location=location,
                    work_location=location,
                    description=description[:5000],
                    posted_at=posted_at,
                    source_timestamp_raw=raw_ts,
                    timestamp_reliable=reliable,
                    last_checked_at=now_utc,
                    remote_type=remote_type,
                    employment_type=employment_type,
                )
            )

        return jobs

    def _fetch_detail_jsonld(self, url: str) -> Optional[dict]:
        try:
            resp = get(url, timeout=20, check_robots=True, use_cache=True)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup.find_all("script", type="application/ld+json"):
                raw = (tag.string or "").strip()
                if not raw:
                    continue
                data = json.loads(raw)
                candidates = data.get("@graph", [data]) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                for item in candidates:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        return item
        except Exception as exc:
            self.logger.debug("SawaTech detail fetch skipped for %s: %s", url, exc)
        return None

    def _extract_ld_location(self, ld: dict) -> str:
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
                clean = ", ".join(p for p in parts if p)
                if clean:
                    return clean
        return ""

