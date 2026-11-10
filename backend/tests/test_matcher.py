"""
Unit tests for the Job Matching and Scoring Engine.
Verifies keyword recognition, skill scoring, exclusions, remote classification, and sponsorship.
"""
import pytest
from backend.core.matcher import JobMatcher, MatchConfig
from backend.core.models import JobListing, MatchCategory, RemoteType, SponsorshipStatus


@pytest.fixture
def matcher():
    return JobMatcher()


def make_job(title: str, description: str = "", location: str = "") -> JobListing:
    return JobListing(
        source="test",
        source_id="test-001",
        url="https://example.com/job/1",
        title=title,
        company="TestCo",
        location=location,
        description=description,
    )


class TestTitleMatching:
    def test_ux_designer_matches(self, matcher):
        job = make_job("UX Designer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.DESIGN

    def test_product_designer_matches(self, matcher):
        job = make_job("Senior Product Designer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.DESIGN

    def test_ui_ux_matches(self, matcher):
        job = make_job("UI/UX Designer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.DESIGN

    def test_frontend_developer_matches(self, matcher):
        job = make_job("Frontend Developer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.FRONTEND

    def test_react_developer_matches(self, matcher):
        job = make_job("React Developer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.FRONTEND

    def test_nextjs_developer_matches(self, matcher):
        job = make_job("Next.js Developer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.FRONTEND

    def test_wordpress_developer_matches(self, matcher):
        job = make_job("WordPress Developer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.WORDPRESS

    def test_web_designer_matches(self, matcher):
        job = make_job("Web Designer")
        matcher.match(job)
        assert job.match_score >= 50

    def test_design_engineer_matches(self, matcher):
        job = make_job("Design Engineer")
        matcher.match(job)
        assert job.match_score >= 50
        assert job.match_category == MatchCategory.DESIGN


class TestExclusions:
    def test_data_scientist_excluded(self, matcher):
        job = make_job("Data Scientist")
        matcher.match(job)
        assert job.match_score == 0
        assert job.match_category == MatchCategory.IRRELEVANT

    def test_sales_excluded(self, matcher):
        job = make_job("Account Executive - Sales")
        matcher.match(job)
        assert job.match_score == 0

    def test_devops_excluded(self, matcher):
        job = make_job("DevOps Engineer")
        matcher.match(job)
        assert job.match_score == 0

    def test_nurse_excluded(self, matcher):
        job = make_job("Registered Nurse")
        matcher.match(job)
        assert job.match_score == 0


class TestSkillScoring:
    def test_figma_skill_boosts_score(self, matcher):
        job = make_job("UX Designer", description="Must know Figma and Sketch")
        matcher.match(job)
        assert job.match_score >= 60

    def test_react_in_description_boosts_frontend(self, matcher):
        job = make_job("Frontend Developer", description="React, TypeScript, Next.js required")
        matcher.match(job)
        assert job.match_score >= 70

    def test_design_system_boosts_score(self, matcher):
        job = make_job("Product Designer", description="Building a design system in Figma")
        matcher.match(job)
        assert job.match_score >= 70


class TestRemoteDetection:
    def test_worldwide_remote_detected(self, matcher):
        job = make_job("UX Designer", description="Work from anywhere in the world. 100% remote.")
        matcher.match(job)
        assert job.remote_type == RemoteType.WORLDWIDE

    def test_restricted_remote_detected(self, matcher):
        job = make_job("Frontend Developer", description="Remote — US only")
        matcher.match(job)
        assert job.remote_type == RemoteType.RESTRICTED

    def test_onsite_detected(self, matcher):
        job = make_job("UI Designer", description="In office, San Francisco onsite role")
        matcher.match(job)
        assert job.remote_type == RemoteType.ONSITE

    def test_worldwide_remote_gets_bonus(self, matcher):
        job_world = make_job("UX Designer", description="Fully remote, work from anywhere")
        job_onsite = make_job("UX Designer", description="In-office only, San Francisco")
        matcher.match(job_world)
        matcher.match(job_onsite)
        assert job_world.match_score > job_onsite.match_score


class TestSponsorshipDetection:
    def test_visa_sponsorship_detected(self, matcher):
        job = make_job("UX Designer", description="We offer visa sponsorship for the right candidate.")
        matcher.match(job)
        assert job.sponsorship == SponsorshipStatus.SPONSORED

    def test_no_sponsorship_detected(self, matcher):
        job = make_job("Frontend Developer", description="Must be authorized to work. No sponsorship.")
        matcher.match(job)
        assert job.sponsorship == SponsorshipStatus.NOT_SPONSORED

    def test_unknown_sponsorship(self, matcher):
        job = make_job("Product Designer")
        matcher.match(job)
        assert job.sponsorship == SponsorshipStatus.UNKNOWN

    def test_sponsorship_boosts_score(self, matcher):
        job_sponsor = make_job("UX Designer", description="Visa sponsorship available worldwide")
        job_no = make_job("UX Designer")
        matcher.match(job_sponsor)
        matcher.match(job_no)
        assert job_sponsor.match_score > job_no.match_score


class TestSeniorityExtraction:
    def test_senior_detected(self, matcher):
        job = make_job("Senior UX Designer")
        matcher.match(job)
        assert job.seniority == "senior"

    def test_junior_detected(self, matcher):
        job = make_job("Junior Frontend Developer")
        matcher.match(job)
        assert job.seniority == "junior"

    def test_lead_detected(self, matcher):
        job = make_job("Design Lead")
        matcher.match(job)
        assert job.seniority == "lead"


class TestMatchReasons:
    def test_reasons_populated(self, matcher):
        job = make_job("UX Designer", description="Figma, design systems, user research")
        matcher.match(job)
        assert len(job.match_reasons) > 0

    def test_exclusion_reason_given(self, matcher):
        job = make_job("Data Scientist")
        matcher.match(job)
        assert any("Excluded" in r for r in job.match_reasons)

