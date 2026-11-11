"""
End-to-end pipeline tests for the Strict 24-Hour Posting Age Filter in collector.py.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from backend.adapters.base import AdapterResult
from backend.core.config import Config
from backend.core.matcher import JobMatcher
from backend.core.models import JobListing, RemoteType


def _build_job(
    source_id: str,
    title: str,
    posted_at=None,
    updated_at=None,
    timestamp_reliable: bool = True,
) -> JobListing:
    return JobListing(
        source="mock_source",
        source_id=source_id,
        url=f"https://example.com/jobs/{source_id}",
        title=title,
        company="ExampleCo",
        location="Remote Worldwide",
        description="Remote worldwide Figma React TypeScript opportunity",
        posted_at=posted_at,
        updated_at=updated_at,
        source_timestamp_raw=posted_at.isoformat() if posted_at else "",
        timestamp_reliable=timestamp_reliable,
        remote_type=RemoteType.WORLDWIDE,
    )


def test_collector_enforces_24h_rule_and_logs_exclusions(tmp_path, monkeypatch):
    now = datetime.now(timezone.utc)
    state_file = tmp_path / "job_state.json"

    jobs = [
        _build_job("3h", "UX Designer", posted_at=now - timedelta(hours=3)),
        _build_job("20h", "Frontend Developer", posted_at=now - timedelta(hours=20)),
        _build_job("25h", "Product Designer", posted_at=now - timedelta(hours=25)),
        _build_job("missing", "UI Designer", posted_at=None, timestamp_reliable=False),
        _build_job(
            "updated_only",
            "React Developer",
            posted_at=None,
            updated_at=now - timedelta(hours=1),
            timestamp_reliable=False,
        ),
    ]

    mock_adapter = MagicMock()
    mock_adapter.DISPLAY_NAME = "MockSource"
    mock_adapter.run.return_value = AdapterResult(source="mock_source", success=True, jobs=jobs)

    cfg = Config(
        state_file_path=str(state_file),
        gmail_credentials_json='{"installed":{"client_id":"x"}}',
        gmail_token_json='{"token":"x","refresh_token":"r","client_id":"x","client_secret":"s"}',
        notification_email="user@example.com",
        min_match_score=40,
        notification_min_score=50,
        max_posting_age_hours=24.0,
    )

    sent_payloads = []

    class FakeGmailNotifier:
        def __init__(self, **kwargs):
            pass

        def send_digest(self, digest_jobs, to_email=""):
            sent_payloads.append(digest_jobs)
            return True

    with (
        patch("backend.core.config.get_config", return_value=cfg),
        patch("backend.adapters.registry.load_sources_config", return_value={}),
        patch("backend.adapters.registry.get_enabled_adapters", return_value=[mock_adapter]),
        patch("backend.core.notifier.GmailNotifier", FakeGmailNotifier),
    ):
        from backend.collector import run_collection

        run_collection()

    assert len(sent_payloads) == 1
    notified_ids = {j["source_id"] for j in sent_payloads[0]}
    assert notified_ids == {"3h", "20h"}

    import json
    state = json.loads(state_file.read_text(encoding="utf-8"))
    stored_ids = {v["source_id"] for v in state["jobs"].values()}
    assert stored_ids == {"3h", "20h"}
    excluded_ids = {r["source_id"] for r in state.get("recent_exclusions", [])}
    assert {"25h", "missing", "updated_only"}.issubset(excluded_ids)


def test_collector_pre_notification_recheck_blocks_expired_job(tmp_path):
    now = datetime.now(timezone.utc)
    state_file = tmp_path / "job_state.json"

    jobs = [
        _build_job("fresh", "UX Designer", posted_at=now - timedelta(hours=2)),
        _build_job("borderline", "Frontend Developer", posted_at=now - timedelta(hours=23, minutes=59)),
    ]

    mock_adapter = MagicMock()
    mock_adapter.DISPLAY_NAME = "MockSource"
    mock_adapter.run.return_value = AdapterResult(source="mock_source", success=True, jobs=jobs)

    cfg = Config(
        state_file_path=str(state_file),
        gmail_credentials_json='{"installed":{"client_id":"x"}}',
        gmail_token_json='{"token":"x","refresh_token":"r","client_id":"x","client_secret":"s"}',
        notification_email="user@example.com",
        min_match_score=40,
        notification_min_score=50,
        max_posting_age_hours=24.0,
    )

    sent_payloads = []

    class FakeGmailNotifier:
        def __init__(self, **kwargs):
            pass

        def send_digest(self, digest_jobs, to_email=""):
            sent_payloads.append(digest_jobs)
            return True

    original_eval = JobMatcher.evaluate_posting_age
    call_counts: dict[str, int] = {}

    def spy_eval(self, job, now=None):
        call_counts[job.source_id] = call_counts.get(job.source_id, 0) + 1
        # Simulate the borderline job aging past 24h by the time digest is sent
        if job.source_id == "borderline" and call_counts[job.source_id] >= 2:
            job.age_filter_passed = False
            job.exclusion_reason = "Expired before email digest send"
            return False, job.exclusion_reason
        return original_eval(self, job, now=now)

    with (
        patch("backend.core.config.get_config", return_value=cfg),
        patch("backend.adapters.registry.load_sources_config", return_value={}),
        patch("backend.adapters.registry.get_enabled_adapters", return_value=[mock_adapter]),
        patch("backend.core.notifier.GmailNotifier", FakeGmailNotifier),
        patch.object(JobMatcher, "evaluate_posting_age", spy_eval),
    ):
        from backend.collector import run_collection

        run_collection()

    assert len(sent_payloads) == 1
    notified_ids = [j["source_id"] for j in sent_payloads[0]]
    assert notified_ids == ["fresh"]

