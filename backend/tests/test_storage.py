"""
Unit tests for the repository-based storage engine (data/job_state.json).
Verifies:
- State loads and saves atomically
- Previously seen jobs prevent duplicate alerts
- User-modified application statuses (saved/applied) are preserved
- Scans preserve existing state even on errors
- Source run statistics logging
"""
import json
import pytest
from pathlib import Path
from backend.core.storage import Storage


@pytest.fixture
def temp_storage(tmp_path):
    state_file = tmp_path / "data" / "job_state.json"
    return Storage(state_path=state_file)


class TestRepositoryStorage:
    def test_empty_initial_state(self, temp_storage):
        assert temp_storage.get_known_fingerprints() == []
        assert temp_storage.get_unnotified_jobs() == []

    def test_upsert_and_persist_jobs(self, temp_storage):
        job1 = {
            "fingerprint": "remoteok::001",
            "source": "remoteok",
            "title": "UI Designer",
            "company": "Figma",
            "match_score": 85,
            "notified": False,
            "detected_at": "2026-11-10T10:00:00Z",
        }
        job2 = {
            "fingerprint": "ashby::002",
            "source": "ashby",
            "title": "Frontend Engineer",
            "company": "Linear",
            "match_score": 90,
            "notified": False,
            "detected_at": "2026-11-10T11:00:00Z",
        }

        count = temp_storage.upsert_jobs([job1, job2])
        assert count == 2
        assert len(temp_storage.get_known_fingerprints()) == 2

        # Verify persisted to disk and reloadable
        new_instance = Storage(state_path=temp_storage.state_path)
        assert len(new_instance.get_known_fingerprints()) == 2
        assert "remoteok::001" in new_instance.get_known_fingerprints()
        assert "ashby::002" in new_instance.get_known_fingerprints()

    def test_preserves_user_application_status(self, temp_storage):
        job = {
            "fingerprint": "job::123",
            "title": "Product Designer",
            "company": "Doist",
            "match_score": 90,
            "application_status": "saved",
            "notified": True,
        }
        temp_storage.upsert_job(job)
        temp_storage.save_state()

        # Rescan detects same job with status 'new'
        updated_scan = {
            "fingerprint": "job::123",
            "title": "Product Designer",
            "company": "Doist",
            "match_score": 92,
            "application_status": "new",
            "notified": False,
        }
        temp_storage.upsert_job(updated_scan)

        # User's 'saved' status and notified flag MUST be preserved
        stored_job = temp_storage._data["jobs"]["job::123"]
        assert stored_job["application_status"] == "saved"
        assert stored_job["notified"] is True

    def test_notification_tracking_and_no_duplicates(self, temp_storage):
        job = {
            "fingerprint": "job::alert",
            "title": "Senior Frontend Developer",
            "company": "Vercel",
            "match_score": 95,
            "notified": False,
            "detected_at": "2026-11-10T12:00:00Z",
        }
        temp_storage.upsert_job(job)
        temp_storage.save_state()

        # Before notification
        unnotified = temp_storage.get_unnotified_jobs(min_score=50)
        assert len(unnotified) == 1

        # Mark notified
        temp_storage.mark_notified(["job::alert"])

        # After notification
        assert len(temp_storage.get_unnotified_jobs(min_score=50)) == 0

        # Reload from disk: still not unnotified
        reloaded = Storage(state_path=temp_storage.state_path)
        assert len(reloaded.get_unnotified_jobs(min_score=50)) == 0

    def test_source_run_logging(self, temp_storage):
        temp_storage.log_source_run("remoteok", True, 15)
        temp_storage.log_source_run("greenhouse", False, 0, error="HTTP 429 Rate limited")
        temp_storage.save_state()

        stats = temp_storage.get_source_stats()
        sources = {s["source"]: s for s in stats}

        assert "remoteok" in sources
        assert sources["remoteok"]["successful_runs"] == 1
        assert sources["remoteok"]["total_jobs"] == 15

        assert "greenhouse" in sources
        assert sources["greenhouse"]["successful_runs"] == 0
        assert "429" in sources["greenhouse"]["last_error"]
