"""
Unit tests for Source Adapters using mocked network responses.
"""
import pytest
from unittest.mock import patch, MagicMock
from backend.adapters.remoteok import RemoteOKAdapter
from backend.adapters.remotive import RemotiveAdapter
from backend.adapters.weworkremotely import WeWorkRemotelyAdapter
from backend.adapters.greenhouse import GreenhouseAdapter
from backend.core.models import RemoteType


SAMPLE_REMOTEOK = [
    {"legal": "disclaimer"},
    {
        "id": "111222",
        "position": "UX Designer",
        "company": "Acme Corp",
        "url": "https://remoteok.com/remote-jobs/111222",
        "date": "2024-03-15T10:00:00Z",
        "location": "Worldwide",
        "tags": ["figma", "ux", "remote"],
        "salary_min": 60000,
        "salary_max": 90000,
        "description": "Looking for a UX Designer with Figma experience.",
    },
    {
        "id": "333444",
        "position": "React Developer",
        "company": "StartupXYZ",
        "url": "https://remoteok.com/remote-jobs/333444",
        "date": "2024-03-14T08:00:00Z",
        "tags": ["react", "javascript", "remote"],
        "salary_min": None,
        "salary_max": None,
    },
]

SAMPLE_REMOTIVE = {
    "jobs": [
        {
            "id": 999,
            "title": "Frontend Developer",
            "company_name": "TechStartup",
            "url": "https://remotive.com/job/999",
            "publication_date": "2024-03-10T12:00:00Z",
            "candidate_required_location": "Worldwide",
            "job_type": "full_time",
            "salary": "$70,000 - $95,000",
            "description": "React, TypeScript, Next.js required.",
            "tags": ["react", "typescript"],
        }
    ]
}

SAMPLE_GREENHOUSE = {
    "jobs": [
        {
            "id": 777,
            "title": "Product Designer",
            "absolute_url": "https://boards.greenhouse.io/figma/jobs/777",
            "location": {"name": "Remote"},
            "departments": [{"name": "Design"}],
            "content": "We are looking for a Product Designer...",
            "updated_at": "2024-03-12T09:00:00Z",
        }
    ]
}


class TestRemoteOKAdapter:
    @patch("backend.adapters.remoteok.get_json")
    def test_fetches_and_normalizes(self, mock_get_json):
        mock_get_json.return_value = SAMPLE_REMOTEOK
        adapter = RemoteOKAdapter()
        result = adapter.run()

        assert result.success is True
        assert len(result.jobs) == 2
        ux_job = next(j for j in result.jobs if j.source_id == "111222")
        assert ux_job.title == "UX Designer"
        assert ux_job.company == "Acme Corp"
        assert ux_job.salary_min == 60000
        assert ux_job.salary_max == 90000
        assert ux_job.remote_type == RemoteType.WORLDWIDE

    @patch("backend.adapters.remoteok.get_json")
    def test_handles_network_error(self, mock_get_json):
        mock_get_json.side_effect = Exception("Connection timed out")
        adapter = RemoteOKAdapter()
        result = adapter.run()

        assert result.success is False
        assert "timed out" in result.error


class TestRemotiveAdapter:
    @patch("backend.adapters.remotive.get_json")
    def test_fetches_jobs(self, mock_get_json):
        mock_get_json.return_value = SAMPLE_REMOTIVE
        adapter = RemotiveAdapter()
        result = adapter.run()

        assert result.success is True
        assert len(result.jobs) >= 1
        job = result.jobs[0]
        assert job.title == "Frontend Developer"
        assert job.salary_min == 70000
        assert job.salary_max == 95000


class TestGreenhouseAdapter:
    @patch("backend.adapters.greenhouse.get_json")
    def test_fetches_company_boards_updated_only_not_treated_as_posted(self, mock_get_json):
        mock_get_json.return_value = SAMPLE_GREENHOUSE
        adapter = GreenhouseAdapter(config={})
        adapter._boards = [("figma", "Figma")]
        result = adapter.run()

        assert result.success is True
        assert len(result.jobs) == 1
        job = result.jobs[0]
        assert job.title == "Product Designer"
        assert job.company == "Figma"
        assert job.posted_at is None
        assert job.updated_at is not None
        assert job.timestamp_reliable is False

    @patch("backend.adapters.greenhouse.get_json")
    def test_greenhouse_uses_first_published_as_posted_at(self, mock_get_json):
        mock_get_json.return_value = {
            "jobs": [
                {
                    "id": 888,
                    "title": "Design Engineer",
                    "absolute_url": "https://boards.greenhouse.io/figma/jobs/888",
                    "location": {"name": "Remote"},
                    "departments": [{"name": "Engineering"}],
                    "content": "Design systems role",
                    "first_published": "2026-11-11T10:00:00Z",
                    "updated_at": "2026-11-11T11:30:00Z",
                }
            ]
        }
        adapter = GreenhouseAdapter(config={})
        adapter._boards = [("figma", "Figma")]
        result = adapter.run()

        assert result.success is True
        assert len(result.jobs) == 1
        job = result.jobs[0]
        assert job.posted_at is not None
        assert job.posted_at.hour == 10
        assert job.timestamp_reliable is True

