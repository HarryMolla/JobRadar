"""
Unit tests for UAE adapters, HTTP failure handling, and the UAE source catalog.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.adapters.hays_uae import HaysUAEAdapter
from backend.adapters.prism_digital import PrismDigitalAdapter
from backend.adapters.sawatech import SawaTechAdapter
from backend.adapters.uae_sources import UAE_SOURCE_CATALOG, build_uae_source_status
from backend.core.http_client import PermanentHTTPError, get as http_get, clear_cache
from backend.core.matcher import JobMatcher
from backend.core.models import BenefitStatus, MatchCategory


def _fake_response(status_code: int = 200, text: str = "", content: bytes = b"") -> MagicMock:
    resp = MagicMock(spec=requests.Response)
    resp.status_code = status_code
    resp.text = text
    resp.content = content if content else text.encode("utf-8")
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


class TestSawaTechAdapter:
    def test_fetches_rss_with_detail_jsonld_and_uae_offset_to_utc(self):
        now_utc = datetime.now(timezone.utc)
        fresh_dubai = (now_utc - timedelta(hours=3)).astimezone(timezone(timedelta(hours=4)))
        stale_dubai = (now_utc - timedelta(hours=96)).astimezone(timezone(timedelta(hours=4)))

        rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Senior UI/UX Designer</title>
    <link>https://www.sawatech.com/jobs/senior-ui-ux-designer/</link>
    <pubDate>{format_datetime(fresh_dubai)}</pubDate>
    <description>Design digital products in Dubai.</description>
  </item>
  <item>
    <title>Old WordPress Developer</title>
    <link>https://www.sawatech.com/jobs/old-wordpress-dev/</link>
    <pubDate>{format_datetime(stale_dubai)}</pubDate>
    <description>Legacy listing.</description>
  </item>
</channel></rss>""".encode("utf-8")

        detail_html = f"""<html><head><script type="application/ld+json">
        {json.dumps({
            "@type": "JobPosting",
            "title": "Senior UI/UX Designer",
            "datePosted": fresh_dubai.isoformat(),
            "description": "<p>Figma, design systems. Visa sponsorship provided and relocation package available.</p>",
            "employmentType": "FULL_TIME",
            "jobLocation": {"@type": "Place", "address": {"addressLocality": "Dubai", "addressCountry": "AE"}}
        })}
        </script></head></html>"""

        calls = []

        def fake_get(url, **kwargs):
            calls.append(url)
            if url.endswith("/jobs/feed/"):
                return _fake_response(200, content=rss_xml)
            if "senior-ui-ux-designer" in url:
                return _fake_response(200, text=detail_html)
            raise AssertionError(f"Should not fetch stale detail page: {url}")

        with patch("backend.adapters.sawatech.get", side_effect=fake_get):
            jobs = SawaTechAdapter().fetch()

        assert len(jobs) == 2
        # Only RSS + 1 fresh detail page were requested (stale >48h skipped detail fetch)
        assert len(calls) == 2

        fresh_job = jobs[0]
        assert fresh_job.source == "sawatech"
        assert fresh_job.source_name == "SawaTech"
        assert fresh_job.posted_at is not None
        assert fresh_job.posted_at.tzinfo == timezone.utc
        assert fresh_job.timestamp_reliable is True
        assert "Dubai" in fresh_job.location

        matched = JobMatcher().match(fresh_job, now=now_utc)
        assert matched.age_filter_passed is True
        assert matched.match_category == MatchCategory.DESIGN
        assert matched.visa_sponsorship == BenefitStatus.CONFIRMED
        assert matched.relocation_support == BenefitStatus.CONFIRMED
        assert matched.flight_covered == BenefitStatus.NOT_CONFIRMED


class TestPrismDigitalAdapter:
    def test_separates_created_at_from_updated_at_and_enforces_age(self):
        now_utc = datetime.now(timezone.utc)
        created_20h = (now_utc - timedelta(hours=20)).isoformat().replace("+00:00", "Z")
        updated_1h = (now_utc - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        stale_created_30h = (now_utc - timedelta(hours=30)).isoformat().replace("+00:00", "Z")

        list_payload = {
            "props": {
                "pageProps": {
                    "initialTotalPages": 1,
                    "initialCareers": [
                        {"_id": "1", "slug": "seo-specialist", "position": "SEO Specialist", "location": "Dubai"},
                        {"_id": "2", "slug": "frontend-dev", "position": "React Developer", "location": "Dubai"},
                    ],
                }
            }
        }
        detail_fresh = {
            "props": {
                "pageProps": {
                    "career": {
                        "_id": "1",
                        "position": "SEO Specialist",
                        "location": "Dubai",
                        "workLocationType": "On-site",
                        "createdAt": created_20h,
                        "updatedAt": updated_1h,
                        "description": "<p>Manage SEO audits, content strategy, and Google Analytics. Visa sponsorship provided.</p>",
                    }
                }
            }
        }
        detail_updated_only = {
            "props": {
                "pageProps": {
                    "career": {
                        "_id": "2",
                        "position": "React Developer",
                        "location": "Dubai",
                        "createdAt": stale_created_30h,
                        "updatedAt": updated_1h,
                        "description": "<p>Build React and Next.js web apps.</p>",
                    }
                }
            }
        }

        def fake_get(url, **kwargs):
            if url == "https://www.prism-me.com/careers":
                html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(list_payload)}</script>'
                return _fake_response(200, text=html)
            if url.endswith("/seo-specialist"):
                html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(detail_fresh)}</script>'
                return _fake_response(200, text=html)
            if url.endswith("/frontend-dev"):
                html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(detail_updated_only)}</script>'
                return _fake_response(200, text=html)
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("backend.adapters.prism_digital.get", side_effect=fake_get):
            jobs = PrismDigitalAdapter().fetch()

        assert len(jobs) == 2
        matcher = JobMatcher()
        seo_job = matcher.match(jobs[0], now=now_utc)
        react_job = matcher.match(jobs[1], now=now_utc)

        # 20h old createdAt passes 24h filter
        assert seo_job.age_filter_passed is True
        assert seo_job.match_category == MatchCategory.MARKETING
        assert seo_job.visa_sponsorship == BenefitStatus.CONFIRMED

        # Updated 1h ago, but original createdAt was 30h ago -> excluded!
        assert react_job.age_filter_passed is False
        assert react_job.match_score == 0


class TestHaysUAEAdapter:
    def test_date_only_excluded_while_verified_3h_utc_included(self):
        now_utc = datetime.now(timezone.utc)
        fresh_3h = (now_utc - timedelta(hours=3)).isoformat().replace("+00:00", "Z")

        search_html = """
        <a href="/job-detail/product-designer_101">Product Designer</a>
        <a href="/job-detail/graphic-designer_102">Graphic Designer</a>
        """
        detail_101 = f"""<script type="application/ld+json">
        {json.dumps({
            "@type": "JobPosting",
            "title": "Product Designer",
            "datePosted": fresh_3h,
            "hiringOrganization": {"name": "Dubai Fintech"},
            "description": "<p>Figma UI/UX product design in Abu Dhabi with visa sponsorship and flight ticket provided.</p>",
            "jobLocation": {"@type": "Place", "address": {"addressLocality": "Abu Dhabi", "addressCountry": "AE"}}
        })}
        </script>"""
        detail_102 = f"""<script type="application/ld+json">
        {json.dumps({
            "@type": "JobPosting",
            "title": "Graphic Designer",
            "datePosted": "2026-11-11",
            "hiringOrganization": {"name": "Creative Studio"},
            "description": "<p>Brand designer role in Dubai.</p>",
            "jobLocation": {"@type": "Place", "address": {"addressLocality": "Dubai", "addressCountry": "AE"}}
        })}
        </script>"""

        def fake_get(url, **kwargs):
            if url == "https://www.hays.ae/job-search":
                return _fake_response(200, text=search_html)
            if url.endswith("product-designer_101"):
                return _fake_response(200, text=detail_101)
            if url.endswith("graphic-designer_102"):
                return _fake_response(200, text=detail_102)
            raise AssertionError(f"Unexpected URL: {url}")

        with patch("backend.adapters.hays_uae.get", side_effect=fake_get):
            jobs = HaysUAEAdapter().fetch()

        assert len(jobs) == 2
        matcher = JobMatcher()

        verified_job = matcher.match(jobs[0], now=now_utc)
        date_only_job = matcher.match(jobs[1], now=now_utc)

        assert verified_job.age_filter_passed is True
        assert verified_job.work_location == "Abu Dhabi, UAE"
        assert verified_job.visa_sponsorship == BenefitStatus.CONFIRMED
        assert verified_job.flight_covered == BenefitStatus.CONFIRMED
        assert verified_job.accommodation_covered == BenefitStatus.NOT_CONFIRMED

        assert date_only_job.timestamp_reliable is False
        assert date_only_job.age_filter_passed is False
        assert date_only_job.match_score == 0


class TestHttpFailureAndCatalogStatus:
    def test_http_403_fails_fast_without_retries(self):
        clear_cache()
        mock_session = MagicMock()
        mock_session.get.return_value = _fake_response(403, text="Forbidden")

        with patch("backend.core.http_client.is_allowed", return_value=True), \
             patch("backend.core.http_client._rate_limiter.wait"):
            with pytest.raises(PermanentHTTPError):
                http_get(
                    "https://blocked.example.ae/jobs",
                    check_robots=True,
                    session=mock_session,
                    delay=0,
                )

        # Must fail on first attempt without 3x retry loop
        assert mock_session.get.call_count == 1

    def test_adapter_failure_never_marks_source_successful(self):
        with patch("backend.adapters.hays_uae.get", side_effect=requests.Timeout("timed out")):
            result = HaysUAEAdapter().run()

        assert result.success is False
        assert "timed out" in (result.error or "")

        statuses = build_uae_source_status([
            {
                "source": "hays_uae",
                "checked_at": "2026-11-11T06:00:00+00:00",
                "success": False,
                "jobs_found": 0,
                "error": result.error,
            }
        ])
        hays_status = next(s for s in statuses if s["id"] == "hays_uae")
        assert hays_status["last_success"] is False
        assert "timed out" in hays_status["last_error"]

    def test_uae_source_catalog_covers_all_19_sources(self):
        assert len(UAE_SOURCE_CATALOG) == 19
        ids = {entry["id"] for entry in UAE_SOURCE_CATALOG}
        expected = {
            "bayt", "indeed_uae", "dubizzle", "gulftalent", "naukrigulf",
            "linkedin_uae", "founditgulf", "glassdoor_uae", "laimoon", "gulfnews",
            "dubaicareers", "tamm_abudhabi", "fahr", "sharjah_hr",
            "michaelpage_uae", "hays_uae",
            "emirates_group", "sawatech", "prism_digital",
        }
        assert ids == expected

