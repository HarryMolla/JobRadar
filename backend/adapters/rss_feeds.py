"""
Generic RSS/Atom feed adapter for employer career pages and aggregators.
Configure feeds in sources_config.yaml under rss_feeds.
"""
from __future__ import annotations

import logging
from calendar import timegm
from datetime import datetime, timezone
from typing import Optional

import feedparser

from backend.adapters.base import BaseAdapter
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp

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

        updated_at = None
        if entry.get("updated"):
            updated_at, upd_raw, _ = parse_utc_timestamp(entry.get("updated"))
            if not raw_ts:
                raw_ts = upd_raw

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
            updated_at=updated_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
        )
