"""
Generic RSS/Atom feed adapter for employer career pages and aggregators.
Configure feeds in sources_config.yaml under rss_feeds.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from time import mktime
from typing import Optional

import feedparser

from backend.adapters.base import BaseAdapter
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)

# Built-in feeds that don't require config
DEFAULT_FEEDS = [
    {
        "url": "https://stackoverflow.com/jobs/feed?r=true&tags=javascript%2Ctypescript%2Creact",
        "source_name": "stackoverflow",
        "company": "",
        "remote_type": "remote_restricted",
    },
    {
        "url": "https://dev.to/feed/tag/hiring",
        "source_name": "devto_hiring",
        "company": "",
        "remote_type": "unknown",
    },
]


class RSSFeedsAdapter(BaseAdapter):
    SOURCE_ID = "rss_feeds"
    DISPLAY_NAME = "RSS Job Feeds"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._feeds = list(DEFAULT_FEEDS) + self.config.get("rss_feeds", [])

    def fetch(self) -> list[JobListing]:
        all_jobs = []
        seen: set[str] = set()

        for feed_config in self._feeds:
            feed_url = feed_config.get("url", "")
            if not feed_url:
                continue
            source_name = feed_config.get("source_name", "rss")
            company = feed_config.get("company", "")
            remote_str = feed_config.get("remote_type", "unknown")
            try:
                remote_type = RemoteType(remote_str)
            except ValueError:
                remote_type = RemoteType.UNKNOWN

            try:
                feed = feedparser.parse(feed_url)
                if not feed.entries:
                    self.logger.warning("RSS empty: %s", feed_url)
                    continue
                self.logger.info("RSS %s: %d entries", source_name, len(feed.entries))
                for entry in feed.entries:
                    link = entry.get("link", "")
                    if not link or link in seen:
                        continue
                    seen.add(link)
                    job = self._normalize(entry, source_name, company, remote_type)
                    if job:
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.error("RSS feed %s failed: %s", feed_url, exc)

        return all_jobs

    def _normalize(
        self,
        entry: dict,
        source_name: str,
        default_company: str,
        remote_type: RemoteType,
    ) -> Optional[JobListing]:
        title = entry.get("title", "")
        url = entry.get("link", "")
        if not title or not url:
            return None

        source_id = url.rstrip("/").split("/")[-1][:64]

        # Try to extract company from title
        company = default_company
        if not company and " at " in title:
            parts = title.rsplit(" at ", 1)
            title = parts[0].strip()
            company = parts[1].strip()

        posted_at = None
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            try:
                posted_at = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
            except Exception:
                pass

        description = entry.get("summary", entry.get("description", ""))

        return JobListing(
            source=source_name,
            source_id=source_id,
            url=url,
            title=title,
            company=company,
            location="Remote",
            description=description[:5000],
            posted_at=posted_at,
            remote_type=remote_type,
        )
