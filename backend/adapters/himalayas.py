"""
Himalayas (himalayas.app) job collector adapter.
Uses Himalayas' public cursor-paginated JSON API (https://himalayas.app/jobs/api)
and permitted keyword search endpoints without ?page= parameters, honoring robots.txt.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from bs4 import BeautifulSoup

from backend.adapters.base import BaseAdapter
from backend.core.http_client import get_json
from backend.core.models import JobListing, RemoteType
from backend.core.time_utils import parse_utc_timestamp
from backend.core.url_utils import clean_job_url, is_valid_job_url, resolve_job_urls

logger = logging.getLogger(__name__)

BROWSE_API_URL = "https://himalayas.app/jobs/api"
SEARCH_API_URL = "https://himalayas.app/jobs/api/search"
DEFAULT_SEARCH_QUERIES = [
    "UI UX Designer",
    "Frontend Developer",
    "WordPress Developer",
    "Digital Marketing",
]


def _strip_utm_params(url: str) -> str:
    cleaned = clean_job_url(url)
    if not cleaned:
        return ""
    parsed = urlparse(cleaned)
    kept = [(k, v) for k, v in parse_qsl(parsed.query) if not k.lower().startswith("utm_")]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", urlencode(kept), ""))


class HimalayasAdapter(BaseAdapter):
    SOURCE_ID = "himalayas"
    DISPLAY_NAME = "Himalayas"
    ENABLED = True

    def __init__(self, config: Optional[dict] = None):
        super().__init__(config)
        self._max_pages = int(self.config.get("himalayas_max_pages", 5))
        self._page_limit = min(20, int(self.config.get("himalayas_page_limit", 20)))
        self._search_queries = list(
            self.config.get("himalayas_search_queries", DEFAULT_SEARCH_QUERIES)
        )

    def fetch(self) -> list[JobListing]:
        all_jobs: list[JobListing] = []
        seen_ids: set[str] = set()
        now_utc = datetime.now(timezone.utc)
        cursor: Optional[str] = None

        # 1. Browse latest jobs via documented cursor pagination (preferred & robots-safe)
        for page_num in range(self._max_pages):
            params: dict = {"limit": self._page_limit}
            if cursor:
                params["cursor"] = cursor

            data = get_json(
                BROWSE_API_URL,
                params=params,
                timeout=25,
                check_robots=True,
                use_cache=True,
            )
            raw_jobs = data.get("jobs") or []
            if not isinstance(raw_jobs, list) or not raw_jobs:
                break

            oldest_age_hours = 0.0
            for raw in raw_jobs:
                job = self._normalize(raw)
                if job and job.source_id not in seen_ids:
                    seen_ids.add(job.source_id)
                    all_jobs.append(job)
                if job and job.posted_at is not None:
                    age_h = (now_utc - job.posted_at).total_seconds() / 3600.0
                    oldest_age_hours = max(oldest_age_hours, age_h)

            cursor = data.get("nextCursor")
            # Stop paging early once entries are well past the 24h window
            if not cursor or oldest_age_hours > 48.0:
                break

        # 2. Supplement with single-page permitted search queries (no ?page= parameter)
        for query in self._search_queries:
            try:
                data = get_json(
                    SEARCH_API_URL,
                    params={"q": query, "limit": self._page_limit},
                    timeout=25,
                    check_robots=True,
                    use_cache=True,
                )
                for raw in data.get("jobs") or []:
                    job = self._normalize(raw)
                    if job and job.source_id not in seen_ids:
                        seen_ids.add(job.source_id)
                        all_jobs.append(job)
            except Exception as exc:
                self.logger.warning("Himalayas search '%s' skipped: %s", query, exc)

        self.logger.info("Himalayas: parsed %d unique jobs", len(all_jobs))
        return all_jobs

    def _normalize(self, raw: dict) -> Optional[JobListing]:
        title = (raw.get("title") or "").strip()
        company = (raw.get("companyName") or "").strip()
        if not title or not company:
            return None

        detail_candidate = clean_job_url(raw.get("guid"))
        apply_candidate = _strip_utm_params(raw.get("applicationLink") or "")
        primary_url, valid_apply, valid_detail = resolve_job_urls(
            apply_url=apply_candidate,
            detail_url=detail_candidate,
        )
        if not is_valid_job_url(primary_url):
            return None

        slug_part = (valid_detail or primary_url).rstrip("/").split("/")[-1]
        company_slug = (raw.get("companySlug") or company.lower().replace(" ", "-"))[:32]
        source_id = f"hm_{company_slug}_{slug_part}"[:80]

        posted_at, raw_ts, reliable = parse_utc_timestamp(raw.get("pubDate"))

        locs = [str(loc).strip() for loc in (raw.get("locationRestrictions") or []) if str(loc).strip()]
        if not locs:
            location = "Worldwide"
            remote_type = RemoteType.WORLDWIDE
        else:
            location = ", ".join(locs[:5]) + (f" (+{len(locs) - 5} more)" if len(locs) > 5 else "")
            locs_lower = " ".join(locs).lower()
            if "worldwide" in locs_lower or "anywhere" in locs_lower or "global" in locs_lower:
                remote_type = RemoteType.WORLDWIDE
            else:
                remote_type = RemoteType.RESTRICTED

        excerpt = (raw.get("excerpt") or "").strip()
        cats = [str(c).replace("-", " ") for c in (raw.get("categories") or []) if c]
        parent_cats = [str(c) for c in (raw.get("parentCategories") or []) if c]
        body_html = raw.get("description") or ""
        body_text = BeautifulSoup(str(body_html), "html.parser").get_text(" ", strip=True) if body_html else ""

        desc_parts = []
        if parent_cats or cats:
            desc_parts.append("Categories: " + ", ".join((parent_cats + cats)[:8]))
        if excerpt:
            desc_parts.append(excerpt)
        if body_text:
            desc_parts.append(body_text)
        description = "\n\n".join(desc_parts)[:5000]

        salary_min = None
        salary_max = None
        try:
            if raw.get("minSalary") is not None:
                salary_min = int(raw["minSalary"])
        except (ValueError, TypeError):
            pass
        try:
            if raw.get("maxSalary") is not None:
                salary_max = int(raw["maxSalary"])
        except (ValueError, TypeError):
            pass

        seniority_list = [str(s).strip().lower() for s in (raw.get("seniority") or []) if s]

        return JobListing(
            source=self.SOURCE_ID,
            source_name=self.DISPLAY_NAME,
            source_id=source_id,
            url=primary_url,
            source_job_url=valid_detail or primary_url,
            apply_url=valid_apply,
            title=title,
            company=company,
            location=location,
            description=description,
            posted_at=posted_at,
            source_timestamp_raw=raw_ts,
            timestamp_reliable=reliable,
            remote_type=remote_type,
            employment_type=str(raw.get("employmentType") or ""),
            seniority=seniority_list[0] if seniority_list else "",
            salary_min=salary_min,
            salary_max=salary_max,
            salary_currency=str(raw.get("currency") or "USD"),
        )

