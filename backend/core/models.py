"""
Shared data models for the JobRadar system.
All adapters must normalize their output to JobListing.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class RemoteType(str, Enum):
    WORLDWIDE = "remote_worldwide"      # Explicitly open to all countries
    RESTRICTED = "remote_restricted"   # Remote but limited countries
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class SponsorshipStatus(str, Enum):
    SPONSORED = "sponsored"            # Explicitly offers visa sponsorship
    NOT_SPONSORED = "not_sponsored"    # Explicitly states no sponsorship
    UNKNOWN = "unknown"                # Not mentioned


class BenefitStatus(str, Enum):
    CONFIRMED = "confirmed"
    NOT_CONFIRMED = "not_confirmed"
    UNAVAILABLE = "unavailable"


class MatchCategory(str, Enum):
    DESIGN = "design"
    FRONTEND = "frontend"
    WORDPRESS = "wordpress"
    MARKETING = "marketing"
    RELATED = "related"
    IRRELEVANT = "irrelevant"


@dataclass
class JobListing:
    """
    Canonical job representation.
    Every adapter must populate at minimum: title, company, url, source.
    """
    # Identity
    source: str                          # adapter identifier e.g. "remoteok"
    source_id: str                       # source-specific job ID
    url: str                             # direct application / job URL

    # Core fields
    title: str
    company: str
    location: str = ""
    work_location: str = ""              # normalized city/emirate (e.g., Dubai, UAE)
    source_name: str = ""                # human-readable originating website
    source_job_url: str = ""             # original vacancy URL
    description: str = ""
    description_html: str = ""

    # Dates
    posted_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_timestamp_raw: str = ""
    timestamp_reliable: bool = True
    is_repost: bool = False
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    first_seen_at: Optional[datetime] = None
    last_checked_at: Optional[datetime] = None

    # Classification
    remote_type: RemoteType = RemoteType.UNKNOWN
    remote_countries: list[str] = field(default_factory=list)   # if restricted
    sponsorship: SponsorshipStatus = SponsorshipStatus.UNKNOWN
    relocation_offered: bool = False
    visa_sponsorship: BenefitStatus = BenefitStatus.NOT_CONFIRMED
    relocation_support: BenefitStatus = BenefitStatus.NOT_CONFIRMED
    flight_covered: BenefitStatus = BenefitStatus.NOT_CONFIRMED
    accommodation_covered: BenefitStatus = BenefitStatus.NOT_CONFIRMED
    employment_type: str = ""           # full-time, contract, part-time
    seniority: str = ""                 # junior, mid, senior, lead

    # Compensation
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = ""

    # Matching & Age Filter (populated by matcher)
    match_score: int = 0
    match_reasons: list[str] = field(default_factory=list)
    match_category: MatchCategory = MatchCategory.IRRELEVANT
    age_hours: Optional[float] = None
    age_filter_passed: bool = False
    exclusion_reason: str = ""

    # Workflow
    notified: bool = False
    application_status: str = "new"     # new, saved, applied, dismissed

    def __post_init__(self) -> None:
        if not self.source_job_url and self.url:
            self.source_job_url = self.url
        if not self.url and self.source_job_url:
            self.url = self.source_job_url
        if not self.source_name and self.source:
            self.source_name = self.source
        if not self.work_location and self.location:
            self.work_location = self.location
        if self.first_seen_at is None:
            self.first_seen_at = self.detected_at

    @property
    def fingerprint(self) -> str:
        """
        Stable deduplication key.
        Prefer source_id when available, else hash of title+company+url.
        """
        if self.source_id:
            return f"{self.source}::{self.source_id}"
        raw = f"{self.title.lower().strip()}::{self.company.lower().strip()}::{self.url}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "source": self.source,
            "source_name": self.source_name or self.source,
            "source_id": self.source_id,
            "url": self.url,
            "source_job_url": self.source_job_url or self.url,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "work_location": self.work_location or self.location,
            "description": self.description[:5000],
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "source_timestamp_raw": self.source_timestamp_raw,
            "timestamp_reliable": self.timestamp_reliable,
            "is_repost": self.is_repost,
            "detected_at": self.detected_at.isoformat(),
            "first_seen_at": (self.first_seen_at or self.detected_at).isoformat(),
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
            "remote_type": self.remote_type.value,
            "remote_countries": self.remote_countries,
            "sponsorship": self.sponsorship.value,
            "relocation_offered": self.relocation_offered,
            "visa_sponsorship": self.visa_sponsorship.value,
            "relocation_support": self.relocation_support.value,
            "flight_covered": self.flight_covered.value,
            "accommodation_covered": self.accommodation_covered.value,
            "employment_type": self.employment_type,
            "seniority": self.seniority,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "salary_currency": self.salary_currency,
            "match_score": self.match_score,
            "match_reasons": self.match_reasons,
            "match_category": self.match_category.value,
            "age_hours": self.age_hours,
            "age_filter_passed": self.age_filter_passed,
            "exclusion_reason": self.exclusion_reason,
            "notified": self.notified,
            "application_status": self.application_status,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "JobListing":
        """Reconstruct from stored dict."""
        job = cls(
            source=data.get("source", ""),
            source_id=data.get("source_id", ""),
            url=data.get("url", ""),
            title=data.get("title", ""),
            company=data.get("company", ""),
        )
        job.location = data.get("location", "")
        job.work_location = data.get("work_location", job.location)
        job.source_name = data.get("source_name", job.source)
        job.source_job_url = data.get("source_job_url", job.url)
        job.description = data.get("description", "")
        if data.get("posted_at"):
            try:
                job.posted_at = datetime.fromisoformat(data["posted_at"])
            except (ValueError, TypeError):
                pass
        if data.get("updated_at"):
            try:
                job.updated_at = datetime.fromisoformat(data["updated_at"])
            except (ValueError, TypeError):
                pass
        job.source_timestamp_raw = data.get("source_timestamp_raw", "")
        job.timestamp_reliable = data.get("timestamp_reliable", True)
        job.is_repost = data.get("is_repost", False)
        if data.get("detected_at"):
            try:
                job.detected_at = datetime.fromisoformat(data["detected_at"])
            except (ValueError, TypeError):
                pass
        if data.get("first_seen_at"):
            try:
                job.first_seen_at = datetime.fromisoformat(data["first_seen_at"])
            except (ValueError, TypeError):
                job.first_seen_at = job.detected_at
        else:
            job.first_seen_at = job.detected_at
        if data.get("last_checked_at"):
            try:
                job.last_checked_at = datetime.fromisoformat(data["last_checked_at"])
            except (ValueError, TypeError):
                pass
        job.remote_type = RemoteType(data.get("remote_type", RemoteType.UNKNOWN.value))
        job.remote_countries = data.get("remote_countries", [])
        job.sponsorship = SponsorshipStatus(data.get("sponsorship", SponsorshipStatus.UNKNOWN.value))
        job.relocation_offered = data.get("relocation_offered", False)
        job.visa_sponsorship = BenefitStatus(
            data.get(
                "visa_sponsorship",
                BenefitStatus.CONFIRMED.value
                if job.sponsorship == SponsorshipStatus.SPONSORED
                else BenefitStatus.UNAVAILABLE.value
                if job.sponsorship == SponsorshipStatus.NOT_SPONSORED
                else BenefitStatus.NOT_CONFIRMED.value,
            )
        )
        job.relocation_support = BenefitStatus(
            data.get(
                "relocation_support",
                BenefitStatus.CONFIRMED.value if job.relocation_offered else BenefitStatus.NOT_CONFIRMED.value,
            )
        )
        job.flight_covered = BenefitStatus(data.get("flight_covered", BenefitStatus.NOT_CONFIRMED.value))
        job.accommodation_covered = BenefitStatus(
            data.get("accommodation_covered", BenefitStatus.NOT_CONFIRMED.value)
        )
        job.employment_type = data.get("employment_type", "")
        job.seniority = data.get("seniority", "")
        job.salary_min = data.get("salary_min")
        job.salary_max = data.get("salary_max")
        job.salary_currency = data.get("salary_currency", "")
        job.match_score = data.get("match_score", 0)
        job.match_reasons = data.get("match_reasons", [])
        job.match_category = MatchCategory(data.get("match_category", MatchCategory.IRRELEVANT.value))
        job.age_hours = data.get("age_hours")
        job.age_filter_passed = data.get("age_filter_passed", False)
        job.exclusion_reason = data.get("exclusion_reason", "")
        job.notified = data.get("notified", False)
        job.application_status = data.get("application_status", "new")
        return job
