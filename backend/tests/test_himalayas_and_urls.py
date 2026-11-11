"""
Unit tests for HimalayasAdapter and global direct/detail Apply URL extraction across adapters.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from backend.adapters.ashby import AshbyAdapter
from backend.adapters.himalayas import HimalayasAdapter
from backend.adapters.jobicy import JobicyAdapter
from backend.adapters.lever import LeverAdapter
from backend.adapters.personio import PersonioAdapter
from backend.adapters.recruitee import RecruiteeAdapter
from backend.adapters.registry import ALL_ADAPTERS
from backend.adapters.remoteok import RemoteOKAdapter
from backend.adapters.smartrecruiters import SmartRecruitersAdapter
from backend.adapters.workable import WorkableAdapter
from backend.adapters.workday import WorkdayAdapter
from backend.adapters.ycombinator import YCombinatorAdapter
from backend.core.matcher import JobMatcher
from backend.core.models import JobListing, MatchCategory, RemoteType
from backend.core.notifier import GmailNotifier
from backend.core.url_utils import is_generic_listing_url, is_valid_job_url, resolve_job_urls


class TestUrlUtils:
    def test_rejects_generic_urls_and_accepts_specific_job_urls(self):
        assert is_generic_listing_url("https://company.com") is True
        assert is_generic_listing_url("https://company.com/careers/") is True
        assert is_generic_listing_url("https://company.com/jobs") is True
        assert is_generic_listing_url("https://hays.ae/job-search?q=designer") is True
        assert is_generic_listing_url("https://himalayas.app/apply") is True
        assert is_generic_listing_url("https://apply.workable.com/typeform/j/") is True
        assert is_generic_listing_url("") is True

        assert is_valid_job_url("https://himalayas.app/companies/acme/jobs/product-designer") is True
        assert is_valid_job_url("https://boards.greenhouse.io/figma/jobs/12345") is True
        assert is_valid_job_url("https://ae.indeed.com/viewjob?jk=abc123") is True
        assert is_valid_job_url("https://example.com/job/1") is True

    def test_prefers_direct_apply_url_and_preserves_detail_url(self):
        primary, apply_u, detail_u = resolve_job_urls(
            apply_url="https://jobs.lever.co/acme/123/apply",
            detail_url="https://himalayas.app/companies/acme/jobs/ux-designer",
        )
        assert primary == "https://jobs.lever.co/acme/123/apply"
        assert apply_u == "https://jobs.lever.co/acme/123/apply"
        assert detail_u == "https://himalayas.app/companies/acme/jobs/ux-designer"

        # Generic apply URL is discarded so detail URL becomes primary
        primary2, apply_u2, detail_u2 = resolve_job_urls(
            apply_url="https://acme.com/careers",
            detail_url="https://himalayas.app/companies/acme/jobs/ux-designer",
        )
        assert primary2 == "https://himalayas.app/companies/acme/jobs/ux-designer"
        assert apply_u2 == ""
        assert detail_u2 == "https://himalayas.app/companies/acme/jobs/ux-designer"


class TestHimalayasAdapter:
    def test_registered_in_all_adapters(self):
        assert HimalayasAdapter in ALL_ADAPTERS

    def test_fetches_cursor_feed_enforces_24h_rule_and_preserves_urls(self):
        now = datetime.now(timezone.utc)
        fresh_3h = int((now - timedelta(hours=3)).timestamp())
        fresh_20h = int((now - timedelta(hours=20)).timestamp())
        stale_72h = int((now - timedelta(hours=72)).timestamp())

        called_urls = []

        def fake_get_json(url, params=None, **kwargs):
            called_urls.append((url, dict(params or {})))
            # Never send ?page= under /jobs/* per robots.txt
            assert "page" not in (params or {})
            if url == "https://himalayas.app/jobs/api":
                if not (params or {}).get("cursor"):
                    return {
                        "nextCursor": "cur-2",
                        "jobs": [
                            {
                                "title": "Senior UI/UX Designer",
                                "companyName": "Desert Tech",
                                "companySlug": "desert-tech",
                                "guid": "https://himalayas.app/companies/desert-tech/jobs/senior-ui-ux-designer",
                                "applicationLink": "https://apply.deserttech.ae/roles/ui-ux-1",
                                "pubDate": fresh_3h,
                                "locationRestrictions": ["United Arab Emirates"],
                                "categories": ["UI-UX-Designer"],
                                "parentCategories": ["Design"],
                                "excerpt": "Design web apps in Dubai with Figma and visa sponsorship provided.",
                                "description": "<p>Figma, Design Systems, Prototyping.</p>",
                                "employmentType": "Full Time",
                                "seniority": ["Senior"],
                                "minSalary": 80000,
                                "maxSalary": 110000,
                                "currency": "USD",
                            },
                            {
                                "title": "React Frontend Developer",
                                "companyName": "GlobalSoft",
                                "companySlug": "globalsoft",
                                "guid": "https://himalayas.app/companies/globalsoft/jobs/react-frontend-developer",
                                "applicationLink": "https://himalayas.app/companies/globalsoft/jobs/react-frontend-developer?utm_source=api",
                                "pubDate": fresh_20h,
                                "locationRestrictions": [],
                                "categories": ["React-Developer"],
                                "parentCategories": ["Engineering"],
                                "excerpt": "Work worldwide in React and TypeScript.",
                                "description": "<p>React, Next.js, TypeScript.</p>",
                            },
                            {
                                "title": "Expired Product Designer",
                                "companyName": "OldCo",
                                "companySlug": "oldco",
                                "guid": "https://himalayas.app/companies/oldco/jobs/expired-product-designer",
                                "applicationLink": "https://himalayas.app/companies/oldco/jobs/expired-product-designer",
                                "pubDate": stale_72h,
                                "locationRestrictions": [],
                            },
                        ],
                    }
                raise AssertionError("Should stop cursor pagination early after 72h job")
            return {"jobs": []}

        with patch("backend.adapters.himalayas.get_json", side_effect=fake_get_json):
            adapter = HimalayasAdapter(config={"himalayas_search_queries": ["UI UX Designer"]})
            result = adapter.run()

        assert result.success is True
        assert len(result.jobs) == 3

        matcher = JobMatcher()
        uae_job = matcher.match(result.jobs[0], now=now)
        worldwide_job = matcher.match(result.jobs[1], now=now)
        stale_job = matcher.match(result.jobs[2], now=now)

        assert uae_job.age_filter_passed is True
        assert uae_job.match_category == MatchCategory.DESIGN
        assert uae_job.apply_url == "https://apply.deserttech.ae/roles/ui-ux-1"
        assert uae_job.source_job_url == "https://himalayas.app/companies/desert-tech/jobs/senior-ui-ux-designer"
        assert uae_job.url == "https://apply.deserttech.ae/roles/ui-ux-1"
        assert uae_job.remote_type == RemoteType.RESTRICTED

        assert worldwide_job.age_filter_passed is True
        assert worldwide_job.remote_type == RemoteType.WORLDWIDE
        assert worldwide_job.url == "https://himalayas.app/companies/globalsoft/jobs/react-frontend-developer"

        assert stale_job.age_filter_passed is False
        assert stale_job.match_score == 0

    def test_handles_errors_gracefully(self):
        with patch("backend.adapters.himalayas.get_json", side_effect=RuntimeError("API unreachable")):
            result = HimalayasAdapter().run()
        assert result.success is False
        assert "API unreachable" in result.error


class TestAllAdaptersApplyUrls:
    def test_remoteok_ashby_lever_recruitee_preserve_apply_and_detail_urls(self):
        rk = RemoteOKAdapter()._normalize({
            "id": "10",
            "position": "UI Designer",
            "company": "Acme",
            "url": "https://remoteok.com/remote-jobs/ui-designer-10",
            "apply_url": "https://boards.greenhouse.io/acme/jobs/10",
            "date": "2026-11-11T10:00:00Z",
        })
        assert rk.apply_url == "https://boards.greenhouse.io/acme/jobs/10"
        assert rk.source_job_url == "https://remoteok.com/remote-jobs/ui-designer-10"
        assert rk.url == "https://boards.greenhouse.io/acme/jobs/10"

        ab = AshbyAdapter()._normalize({
            "id": "uuid-1",
            "title": "Product Designer",
            "jobUrl": "https://jobs.ashbyhq.com/linear/uuid-1",
            "applyUrl": "https://jobs.ashbyhq.com/linear/uuid-1/application",
            "publishedDate": "2026-11-11T10:00:00Z",
        }, "Linear")
        assert ab.apply_url == "https://jobs.ashbyhq.com/linear/uuid-1/application"
        assert ab.source_job_url == "https://jobs.ashbyhq.com/linear/uuid-1"
        assert ab.url == ab.apply_url

        lv = LeverAdapter()._normalize({
            "id": "lv-1",
            "text": "Frontend Engineer",
            "hostedUrl": "https://jobs.lever.co/stripe/lv-1",
            "applyUrl": "https://jobs.lever.co/stripe/lv-1/apply",
            "createdAt": 1794400000000,
        }, "Stripe")
        assert lv.apply_url == "https://jobs.lever.co/stripe/lv-1/apply"
        assert lv.source_job_url == "https://jobs.lever.co/stripe/lv-1"
        assert lv.url == lv.apply_url

        rt = RecruiteeAdapter()._normalize({
            "id": "55",
            "slug": "ux-lead",
            "title": "UX Lead",
            "careers_url": "https://remote.recruitee.com/o/ux-lead",
            "careers_apply_url": "https://remote.recruitee.com/o/ux-lead/c/new",
            "published_at": "2026-11-11T10:00:00Z",
        }, "Remote.com", "remote")
        assert rt.apply_url == "https://remote.recruitee.com/o/ux-lead/c/new"
        assert rt.source_job_url == "https://remote.recruitee.com/o/ux-lead"

    def test_missing_or_generic_urls_never_fabricate_generic_careers_links(self):
        sr_missing = SmartRecruitersAdapter()._normalize({"name": "UX Designer"}, "Delivery Hero", "Delivery-Hero")
        assert sr_missing is not None
        assert sr_missing.url == ""

        sr_valid = SmartRecruitersAdapter()._normalize({"id": "744000123", "name": "UX Designer"}, "Delivery Hero", "Delivery-Hero")
        assert sr_valid.url == "https://jobs.smartrecruiters.com/Delivery-Hero/744000123"

        wb_missing = WorkableAdapter()._normalize({"title": "UI Designer"}, "Typeform", "typeform")
        assert wb_missing.url == ""

        yc_missing = YCombinatorAdapter()._normalize({"title": "Web Designer", "company": {"name": "YC Co"}})
        assert yc_missing.url == ""

        jy_missing = JobicyAdapter()._normalize({"id": "99", "jobTitle": "UI Designer", "companyName": "Co"})
        assert jy_missing.url == ""

        wd = WorkdayAdapter()._normalize(
            {"title": "Frontend Dev", "externalPath": "/job/Dubai/Frontend-Dev_R99", "postedOn": "Posted Today"},
            "Adobe",
            "",
            "https://adobe.wd5.myworkdayjobs.com/wday/cxs/adobe/external_experienced/jobs",
        )
        assert wd.url == "https://adobe.wd5.myworkdayjobs.com/external_experienced/job/Dubai/Frontend-Dev_R99"

        import xml.etree.ElementTree as ET
        pos = ET.fromstring("<position><id>42</id><name>UI Designer</name><createdAt>2026-11-11T10:00:00Z</createdAt></position>")
        ps_com = PersonioAdapter()._normalize(pos, "Taxfix", "taxfix", "https://taxfix.jobs.personio.com")
        assert ps_com.url == "https://taxfix.jobs.personio.com/job/42"

    def test_notifier_prefers_apply_url_and_handles_missing_url(self):
        notifier = GmailNotifier("", "", "me@example.com")
        html = notifier._build_html([
            {
                "title": "UI Designer",
                "company": "Acme",
                "apply_url": "https://apply.acme.com/job/1",
                "source_job_url": "https://himalayas.app/companies/acme/jobs/ui",
                "match_score": 80,
            },
            {
                "title": "No Link Role",
                "company": "MysteryCo",
                "url": "",
                "match_score": 60,
            },
        ])
        assert 'href="https://apply.acme.com/job/1"' in html
        assert "Direct link unavailable" in html
        assert 'href="#"' not in html

