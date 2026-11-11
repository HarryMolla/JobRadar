"""
Unit tests for the Job Matching and Scoring Engine.
Verifies keyword recognition, skill scoring, exclusions, remote classification, and sponsorship.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import pytest
from backend.core.matcher import JobMatcher, MatchConfig
from backend.core.models import (
    BenefitStatus,
    JobListing,
    MatchCategory,
    RemoteType,
    SponsorshipStatus,
)
from backend.core.time_utils import parse_utc_timestamp


@pytest.fixture
def matcher():
    return JobMatcher()


_UNSET = object()


def make_job(
    title: str,
    description: str = "",
    location: str = "",
    posted_at: object = _UNSET,
    updated_at: Optional[datetime] = None,
    timestamp_reliable: bool = True,
    is_repost: bool = False,
    source_timestamp_raw: str = "",
) -> JobListing:
    if posted_at is _UNSET:
        resolved_posted_at = datetime.now(timezone.utc) - timedelta(hours=1)
    else:
        resolved_posted_at = posted_at  # type: ignore[assignment]
    return JobListing(
        source="test",
        source_id="test-001",
        url="https://example.com/job/1",
        title=title,
        company="TestCo",
        location=location,
        description=description,
        posted_at=resolved_posted_at,
        updated_at=updated_at,
        timestamp_reliable=timestamp_reliable,
        is_repost=is_repost,
        source_timestamp_raw=source_timestamp_raw,
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


class TestPostingAgeFilter:
    def test_job_posted_3_hours_ago_included(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("UX Designer", description="Figma worldwide remote", posted_at=now - timedelta(hours=3))
        matcher.match(job, now=now)
        assert job.age_filter_passed is True
        assert job.match_score >= 50
        assert job.age_hours == pytest.approx(3.0, abs=0.01)

    def test_job_posted_20_hours_ago_included(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("Frontend Developer", description="React TypeScript", posted_at=now - timedelta(hours=20))
        matcher.match(job, now=now)
        assert job.age_filter_passed is True
        assert job.match_score >= 50
        assert job.age_hours == pytest.approx(20.0, abs=0.01)

    def test_job_posted_25_hours_ago_excluded(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("Product Designer", description="Figma worldwide remote", posted_at=now - timedelta(hours=25))
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0
        assert job.match_category == MatchCategory.IRRELEVANT
        assert job.exclusion_reason

    def test_missing_posted_at_excluded(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("UX Designer", description="Figma remote", posted_at=None, timestamp_reliable=False)
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0
        assert job.exclusion_reason

    def test_unreliable_timestamp_excluded_even_with_datetime(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("UX Designer", posted_at=now - timedelta(hours=2), timestamp_reliable=False)
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0

    def test_updated_at_only_not_treated_as_new_job(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job(
            "UI Designer",
            posted_at=None,
            updated_at=now - timedelta(hours=1),
            timestamp_reliable=False,
            is_repost=False,
        )
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0

    def test_updated_at_with_verified_repost_flag_included(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job(
            "UI Designer",
            posted_at=None,
            updated_at=now - timedelta(hours=2),
            timestamp_reliable=False,
            is_repost=True,
        )
        matcher.match(job, now=now)
        assert job.age_filter_passed is True
        assert job.match_score >= 50

    def test_non_utc_timezone_converted_accurately(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        eat = timezone(timedelta(hours=3))
        posted_eat = (now - timedelta(hours=4)).astimezone(eat)
        job = make_job("React Developer", posted_at=posted_eat)
        matcher.match(job, now=now)
        assert job.age_filter_passed is True
        assert job.age_hours == pytest.approx(4.0, abs=0.01)

    def test_naive_datetime_rejected(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        naive_dt = datetime(2026, 11, 11, 10, 0, 0)
        job = make_job("UX Designer", posted_at=naive_dt)
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0

    def test_future_timestamp_excluded(self, matcher):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        job = make_job("UX Designer", posted_at=now + timedelta(hours=2))
        matcher.match(job, now=now)
        assert job.age_filter_passed is False
        assert job.match_score == 0

    def test_configurable_max_posting_age_hours(self):
        now = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
        strict_matcher = JobMatcher(MatchConfig(max_posting_age_hours=6.0))
        fresh = make_job("UX Designer", posted_at=now - timedelta(hours=4))
        stale = make_job("UX Designer", posted_at=now - timedelta(hours=8))
        strict_matcher.match(fresh, now=now)
        strict_matcher.match(stale, now=now)
        assert fresh.age_filter_passed is True
        assert fresh.match_score >= 50
        assert stale.age_filter_passed is False
        assert stale.match_score == 0

    def test_parse_utc_timestamp_rejects_ambiguous_strings(self):
        dt_date, _, rel_date = parse_utc_timestamp("2026-11-11")
        assert dt_date is None and rel_date is False

        dt_rel, _, rel_flag = parse_utc_timestamp("Posted Today")
        assert dt_rel is None and rel_flag is False

        dt_iso, _, rel_iso = parse_utc_timestamp("2026-11-11T09:00:00Z")
        assert dt_iso == datetime(2026, 11, 11, 9, 0, 0, tzinfo=timezone.utc)
        assert rel_iso is True


class TestExpandedRolesAndUAEBenefits:
    @pytest.mark.parametrize("title", [
        "Graphic Designer",
        "Brand and Visual Designer",
        "Visual Designer",
    ])
    def test_expanded_design_roles_match(self, matcher, title):
        job = make_job(title)
        matcher.match(job)
        assert job.match_category == MatchCategory.DESIGN
        assert job.match_score >= 45

    @pytest.mark.parametrize("title", [
        "Digital Marketing Specialist",
        "SEO Specialist",
        "Social Media Manager",
        "Digital Content Creator",
    ])
    def test_digital_marketing_roles_match(self, matcher, title):
        job = make_job(
            title,
            description="SEO, Google Analytics, social media content creation, Figma campaigns.",
        )
        matcher.match(job)
        assert job.match_category == MatchCategory.MARKETING
        assert job.match_score >= 45

    def test_confirmed_benefits_tracked_separately_and_boost_score(self, matcher):
        base = make_job("Product Designer", description="Figma design systems in Dubai, UAE.")
        rich = make_job(
            "Product Designer",
            description=(
                "Figma design systems in Dubai, UAE. Visa sponsorship provided, "
                "relocation package available, flight ticket covered, and housing allowance included."
            ),
            location="Dubai, UAE",
        )
        matcher.match(base)
        matcher.match(rich)

        assert base.visa_sponsorship == BenefitStatus.NOT_CONFIRMED
        assert base.relocation_support == BenefitStatus.NOT_CONFIRMED
        assert base.flight_covered == BenefitStatus.NOT_CONFIRMED
        assert base.accommodation_covered == BenefitStatus.NOT_CONFIRMED
        assert base.match_score >= 45  # Still included when benefits unverified

        assert rich.visa_sponsorship == BenefitStatus.CONFIRMED
        assert rich.sponsorship == SponsorshipStatus.SPONSORED
        assert rich.relocation_support == BenefitStatus.CONFIRMED
        assert rich.relocation_offered is True
        assert rich.flight_covered == BenefitStatus.CONFIRMED
        assert rich.accommodation_covered == BenefitStatus.CONFIRMED
        assert rich.match_score > base.match_score

    def test_missing_flight_and_accommodation_stay_not_confirmed(self, matcher):
        job = make_job(
            "UI/UX Designer",
            description="Employment visa provided in Abu Dhabi.",
            location="Abu Dhabi, UAE",
        )
        matcher.match(job)
        assert job.visa_sponsorship == BenefitStatus.CONFIRMED
        assert job.relocation_support == BenefitStatus.NOT_CONFIRMED
        assert job.flight_covered == BenefitStatus.NOT_CONFIRMED
        assert job.accommodation_covered == BenefitStatus.NOT_CONFIRMED

    def test_unavailable_benefits_recorded_and_penalized(self, matcher):
        job = make_job(
            "Frontend Developer",
            description="React developer. No visa sponsorship available. No relocation support.",
        )
        matcher.match(job)
        assert job.visa_sponsorship == BenefitStatus.UNAVAILABLE
        assert job.sponsorship == SponsorshipStatus.NOT_SPONSORED
        assert job.relocation_support == BenefitStatus.UNAVAILABLE

    @pytest.mark.parametrize("flight_phrase,acc_phrase", [
        ("flight ticket provided", "accommodation provided"),
        ("company-paid flight", "company-provided accommodation"),
        ("flight tickets are covered", "housing is covered"),
        ("return flight ticket included", "company accommodation"),
    ])
    def test_confirmed_flight_and_accommodation_wording_variants(self, matcher, flight_phrase, acc_phrase):
        job = make_job(
            "UI/UX Designer",
            description=f"Join our Dubai team. Benefits: {flight_phrase}, {acc_phrase}.",
            location="Dubai, UAE",
        )
        matcher.match(job)
        assert job.flight_covered == BenefitStatus.CONFIRMED
        assert job.accommodation_covered == BenefitStatus.CONFIRMED
        assert job.visa_sponsorship == BenefitStatus.NOT_CONFIRMED
        assert job.relocation_support == BenefitStatus.NOT_CONFIRMED

    def test_ambiguous_or_possible_benefits_stay_not_confirmed(self, matcher):
        ambiguous = make_job(
            "Product Designer",
            description=(
                "Flight ticket may be provided depending on experience. "
                "Company-provided accommodation, subject to management approval. "
                "Possible relocation assistance if required."
            ),
        )
        unrelated_possible = make_job(
            "Product Designer",
            description="We create the best possible user experiences. Accommodation provided. Company-paid flight.",
        )
        matcher.match(ambiguous)
        matcher.match(unrelated_possible)

        assert ambiguous.flight_covered == BenefitStatus.NOT_CONFIRMED
        assert ambiguous.accommodation_covered == BenefitStatus.NOT_CONFIRMED
        assert ambiguous.relocation_support == BenefitStatus.NOT_CONFIRMED

        assert unrelated_possible.flight_covered == BenefitStatus.CONFIRMED
        assert unrelated_possible.accommodation_covered == BenefitStatus.CONFIRMED

    @pytest.mark.parametrize("text", [
        "No flight or accommodation provided.",
        "Flights not covered; housing not included.",
        "Flight ticket not provided and accommodation not covered.",
    ])
    def test_explicit_unavailable_flight_and_accommodation(self, matcher, text):
        job = make_job("Frontend Developer", description=f"React engineer role. {text}")
        matcher.match(job)
        assert job.flight_covered == BenefitStatus.UNAVAILABLE
        assert job.accommodation_covered == BenefitStatus.UNAVAILABLE

    @pytest.mark.parametrize("raw_loc,expected_emirate", [
        ("Dubai, United Arab Emirates", "Dubai, UAE"),
        ("Abu Dhabi", "Abu Dhabi, UAE"),
        ("Sharjah, UAE", "Sharjah, UAE"),
        ("Remote - UAE", "UAE"),
    ])
    def test_uae_work_location_normalized(self, matcher, raw_loc, expected_emirate):
        job = make_job("Web Developer", location=raw_loc)
        matcher.match(job)
        assert job.work_location == expected_emirate



