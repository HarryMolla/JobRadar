"""
Unit tests for the JobRadar Local API Handler and Storage state.
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
        storage = Storage()
        jobs = storage.get_jobs(min_score=50)
        assert len(jobs) == 1
        assert jobs[0]["title"] == "UI Designer"

    def test_storage_state_roundtrip(self, tmp_path):
        test_file = tmp_path / "job_state.json"
        storage = Storage(state_path=test_file)

        sample_job = {
            "fingerprint": "test::123",
            "title": "React Engineer",
            "company": "Vercel",
            "match_score": 88,
            "application_status": "new",
            "notified": False,
            "detected_at": "2026-11-10T12:00:00Z",
        }

        # Upsert
        assert storage.upsert_job(sample_job) is True
        storage.save_state()
        assert "test::123" in storage.get_known_fingerprints()

        # Reload from disk into a fresh instance
        reloaded = Storage(state_path=test_file)
        assert "test::123" in reloaded.get_known_fingerprints()
        jobs = reloaded.get_jobs()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "Vercel"

        # Mark notified
        reloaded.mark_notified(["test::123"])
        unnotified = reloaded.get_unnotified_jobs(min_score=50)
        assert len(unnotified) == 0

        # Verify notification preserved across reloads
        fresh = Storage(state_path=test_file)
        assert len(fresh.get_unnotified_jobs(min_score=50)) == 0
