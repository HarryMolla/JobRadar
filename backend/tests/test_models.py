"""
Unit tests for data models and schema conversions.
"""
import pytest
from datetime import datetime, timezone
from backend.core.models import JobListing, RemoteType, SponsorshipStatus, MatchCategory


class TestJobListing:
    def test_fingerprint_uses_source_id(self):
        job = JobListing(
            source="remoteok",
            source_id="12345",
            url="https://remoteok.com/job/12345",
            title="UX Designer",
            company="Acme",
        )
        assert job.fingerprint == "remoteok::12345"

    def test_fingerprint_fallback_hash(self):
        job = JobListing(
            source="test",
            source_id="",
            url="https://example.com/unique-job",
            title="UX Designer",
            company="Acme",
        )
        fp = job.fingerprint
        assert len(fp) == 32
        assert fp.isalnum()

    def test_to_dict_round_trip(self):
        job = JobListing(
            source="remoteok",
            source_id="abc",
            url="https://remoteok.com/job/abc",
            title="Frontend Developer",
            company="TestCo",
            location="Remote",
            match_score=75,
            match_reasons=["Title matches", "React skill"],
            remote_type=RemoteType.WORLDWIDE,
            sponsorship=SponsorshipStatus.SPONSORED,
        )
        d = job.to_dict()
        restored = JobListing.from_dict(d)
        assert restored.title == job.title
        assert restored.company == job.company
        assert restored.match_score == job.match_score
        assert restored.remote_type == RemoteType.WORLDWIDE
        assert restored.sponsorship == SponsorshipStatus.SPONSORED

    def test_description_truncated_in_dict(self):
        long_desc = "x" * 10000
        job = JobListing(
            source="test",
            source_id="1",
            url="https://example.com",
            title="X",
            company="Y",
            description=long_desc,
        )
        d = job.to_dict()
        assert len(d["description"]) <= 5000

    def test_missing_fields_handled(self):
        job = JobListing.from_dict({
            "source": "test",
            "source_id": "1",
            "url": "https://example.com",
            "title": "Designer",
            "company": "Acme",
        })
        assert job.location == ""
        assert job.match_score == 0
        assert job.remote_type == RemoteType.UNKNOWN
        assert job.sponsorship == SponsorshipStatus.UNKNOWN

