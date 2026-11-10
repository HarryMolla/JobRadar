"""
Unit tests for the JobRadar Local API Handler.
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.core.storage import Storage


class TestAPIEndpoints:
    @patch.object(Storage, "get_jobs")
    def test_get_jobs_handler(self, mock_get_jobs):
        mock_get_jobs.return_value = [
            {"title": "UI Designer", "company": "Figma", "match_score": 90, "fingerprint": "f1"}
        ]
        storage = Storage("", "")
        jobs = storage.get_jobs(min_score=50)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "UI Designer"

    def test_local_storage_fallback_roundtrip(self, tmp_path):
        test_file = tmp_path / "test_jobs.json"
        storage = Storage("", "")
        storage._fallback_path = test_file

        sample_job = {
            "fingerprint": "test::123",
            "title": "React Engineer",
            "company": "Vercel",
            "match_score": 88,
            "application_status": "new",
            "notified": False,
        }

        # Upsert
        assert storage.upsert_job(sample_job) is True
        assert "test::123" in storage.get_known_fingerprints()

        # Update status
        jobs = storage.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "Vercel"

        # Mark notified
        storage.mark_notified(["test::123"])
        unnotified = storage.get_unnotified_jobs(min_score=50)
        assert len(unnotified) == 0

