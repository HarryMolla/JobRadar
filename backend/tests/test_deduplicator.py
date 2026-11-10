"""
Unit tests for the Deduplication engine.
"""
import pytest
from unittest.mock import MagicMock
from backend.core.deduplicator import Deduplicator
from backend.core.models import JobListing


def make_job(source_id: str, title: str = "UX Designer") -> JobListing:
    return JobListing(
        source="test",
        source_id=source_id,
        url=f"https://example.com/job/{source_id}",
        title=title,
        company="TestCo",
    )


@pytest.fixture
def mock_storage():
    storage = MagicMock()
    storage.get_known_fingerprints.return_value = []
    return storage


@pytest.fixture
def deduplicator(mock_storage):
    return Deduplicator(mock_storage)


class TestDeduplicator:
    def test_new_job_is_new(self, deduplicator):
        job = make_job("job-001")
        assert deduplicator.is_new(job) is True

    def test_seen_job_is_not_new(self, deduplicator):
        job = make_job("job-001")
        deduplicator.mark_seen(job)
        assert deduplicator.is_new(job) is False

    def test_filter_new_removes_duplicates(self, deduplicator):
        jobs = [make_job("001"), make_job("002"), make_job("001")]
        new = deduplicator.filter_new(jobs)
        fps = [j.fingerprint for j in new]
        assert len(fps) == len(set(fps))

    def test_filter_new_returns_only_unseen(self, deduplicator):
        job1 = make_job("001")
        job2 = make_job("002")
        deduplicator.mark_seen(job1)
        new = deduplicator.filter_new([job1, job2])
        assert len(new) == 1
        assert new[0].source_id == "002"

    def test_fingerprint_stable(self):
        job = make_job("123")
        fp1 = job.fingerprint
        fp2 = job.fingerprint
        assert fp1 == fp2

    def test_different_jobs_different_fingerprints(self):
        job1 = make_job("001")
        job2 = make_job("002")
        assert job1.fingerprint != job2.fingerprint

    def test_loads_fingerprints_from_storage(self):
        storage = MagicMock()
        job = make_job("known-001")
        storage.get_known_fingerprints.return_value = [job.fingerprint]
        d = Deduplicator(storage)
        assert d.is_new(job) is False

    def test_empty_batch_returns_empty(self, deduplicator):
        assert deduplicator.filter_new([]) == []

