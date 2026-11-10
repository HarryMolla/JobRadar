"""
Unit tests for notification message generation and formatting.
"""
import pytest
from backend.core.notifier import GmailNotifier


SAMPLE_JOBS = [
    {
        "fingerprint": "abc123",
        "title": "UX Designer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://example.com/job/1",
        "match_score": 80,
        "match_reasons": ["Title matches UX Designer", "Figma skill (+15)"],
        "remote_type": "remote_worldwide",
        "sponsorship": "sponsored",
        "relocation_offered": False,
        "source": "remoteok",
        "detected_at": "2024-03-15T10:00:00Z",
        "posted_at": "2024-03-14T08:00:00Z",
        "salary_min": 70000,
        "salary_max": 90000,
        "salary_currency": "USD",
    }
]


class TestEmailBuilding:
    def setup_method(self):
        self.notifier = GmailNotifier(
            credentials_json="{}",
            token_json="{}",
            sender_email="test@gmail.com",
        )

    def test_html_contains_job_title(self):
        html = self.notifier._build_html(SAMPLE_JOBS)
        assert "UX Designer" in html

    def test_html_contains_company(self):
        html = self.notifier._build_html(SAMPLE_JOBS)
        assert "Acme Corp" in html

    def test_html_contains_apply_link(self):
        html = self.notifier._build_html(SAMPLE_JOBS)
        assert "https://example.com/job/1" in html

    def test_html_contains_score(self):
        html = self.notifier._build_html(SAMPLE_JOBS)
        assert "80" in html

    def test_html_shows_visa_sponsorship(self):
        html = self.notifier._build_html(SAMPLE_JOBS)
        assert "sponsorship" in html.lower() or "✈️" in html

    def test_text_fallback_contains_title(self):
        text = self.notifier._build_text(SAMPLE_JOBS)
        assert "UX Designer" in text
        assert "Acme Corp" in text

    def test_text_contains_apply_url(self):
        text = self.notifier._build_text(SAMPLE_JOBS)
        assert "https://example.com/job/1" in text

    def test_multiple_jobs_rendering(self):
        jobs = SAMPLE_JOBS * 3
        html = self.notifier._build_html(jobs)
        assert html.count("Apply Now") == 3

