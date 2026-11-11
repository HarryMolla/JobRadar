"""
Dynamite Jobs adapter.
Uses public RSS feed.
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
    "https://dynamitejobs.com/remote-jobs.rss",
    "https://dynamitejobs.com/remote-design-jobs.rss",
]


class DynamiteJobsAdapter(BaseAdapter):
    SOURCE_ID = "dynamitejobs"
    DISPLAY_NAME = "Dynamite Jobs"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                if not feed.entries:
                    self.logger.warning("DynamiteJobs: empty feed from %s", feed_url)
                    continue
                self.logger.info("DynamiteJobs: %d entries from %s", len(feed.entries), feed_url)
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    job = self._normalize(entry)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("DynamiteJobs feed %s failed: %s", feed_url, exc)

        return all_jobs

    def _normalize(self, entry: dict) -> JobListing | None:
        title = entry.get("title", "")
        url = entry.get("link", "")
        if not title or not url:
            return None

        source_id = url.rstrip("/").split("/")[-1]

        # Try to extract company from title
        company = ""
        if " at " in title:
            parts = title.split(" at ", 1)
            title = parts[0].strip()
            company = parts[1].strip()

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

        return JobListing(
            source=self.SOURCE_ID,
            source_id=source_id,
            url=url,
            title=title,
            company=company,
            location="Remote",
            description=entry.get("summary", ""),
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=RemoteType.WORLDWIDE,
        )
