"""
We Work Remotely adapter.
Uses public RSS feeds.
"""
from __future__ import annotations

import logging
from calendar import timegm
from datetime import datetime, timezone

import feedparser

from backend.adapters.base import BaseAdapter
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    ("https://weworkremotely.com/categories/remote-design-jobs.rss", "design"),
    ("https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss", "frontend"),
    ("https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss", "fullstack"),
]


class WeWorkRemotelyAdapter(BaseAdapter):
    SOURCE_ID = "weworkremotely"
    DISPLAY_NAME = "We Work Remotely"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for feed_url, category in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                if feed.bozo and not feed.entries:
                    self.logger.warning("WWR feed parse error for %s: %s", feed_url, feed.bozo_exception)
                    continue
                self.logger.info("WWR %s: %d entries", category, len(feed.entries))
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    job = self._normalize(entry)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("WWR feed %s failed: %s", feed_url, exc)

        return all_jobs

    def _normalize(self, entry: dict) -> JobListing | None:
        title_full = entry.get("title", "")
        # WWR title format: "Company Name: Job Title at Location"
        # Try to split company from title
        company = ""
        title = title_full
        if ": " in title_full:
            parts = title_full.split(": ", 1)
            company = parts[0].strip()
            title = parts[1].strip()
        # Remove "at Location" suffix if present
        if " at " in title:
            title = title.rsplit(" at ", 1)[0].strip()

        url = entry.get("link", "")
        if not title or not url:
            return None

        # Derive source_id from URL
        source_id = url.rstrip("/").split("/")[-1]

        # Published date (use explicit published string or feedparser UTC struct_time)
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

        region = entry.get("region", "") or ""
        location = region if region else "Remote"

        return JobListing(
            source=self.SOURCE_ID,
            source_id=source_id,
            url=url,
            title=title,
            company=company,
            location=location,
            description=entry.get("summary", ""),
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,
        )
