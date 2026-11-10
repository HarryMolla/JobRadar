"""
Dynamite Jobs adapter.
Uses public RSS feed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser

from backend.adapters.base import BaseAdapter
from backend.core.models import JobListing, RemoteType

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

        posted_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                from time import mktime
                posted_at = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
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
            remote_type=RemoteType.WORLDWIDE,
        )
