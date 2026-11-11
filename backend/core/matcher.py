"""
Rule-based job matching engine.
Transparent, configurable, no paid AI required.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from backend.core.models import (
    BenefitStatus,
    JobListing,
    MatchCategory,
    RemoteType,
    SponsorshipStatus,
)
from backend.core.time_utils import to_utc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

DESIGN_TITLE_KEYWORDS = [
    "ui/ux", "ui ux", "ux/ui", "ux designer", "ui designer",
    "product designer", "web designer", "interaction designer",
    "visual designer", "graphic designer", "brand designer",
    "brand and visual designer", "brand & visual designer",
    "figma designer", "ux researcher",
    "user experience", "user interface", "design lead",
    "senior designer", "junior designer", "design engineer",
    "motion designer",  # borderline but keep
]

FRONTEND_TITLE_KEYWORDS = [
    "frontend", "front-end", "front end",
    "react developer", "react engineer",
    "javascript developer", "javascript engineer",
    "typescript developer", "typescript engineer",
    "next.js", "nextjs",
    "vue developer", "vue engineer",
    "angular developer", "angular engineer",
    "ui developer", "ui engineer",
    "web developer", "web engineer",
    "software engineer",  # only when combined with FE skills
]

WORDPRESS_TITLE_KEYWORDS = [
    "wordpress", "wp developer", "wp engineer",
    "elementor", "divi",
]

MARKETING_TITLE_KEYWORDS = [
    "digital marketing specialist", "digital marketing",
    "seo specialist", "social media manager",
    "digital content creator", "content creator",
]

SKILL_KEYWORDS = {
    "figma": 15,
    "sketch": 10,
    "adobe xd": 10,
    "photoshop": 8,
    "illustrator": 8,
    "branding": 8,
    "prototyping": 8,
    "wireframe": 8,
    "design system": 12,
    "component library": 8,
    "responsive design": 8,
    "accessibility": 8,
    "wcag": 10,
    "aria": 6,
    "react": 12,
    "typescript": 10,
    "javascript": 8,
    "next.js": 10,
    "nextjs": 10,
    "html": 6,
    "css": 6,
    "tailwind": 8,
    "sass": 5,
    "storybook": 8,
    "user research": 10,
    "usability testing": 10,
    "a/b testing": 6,
    "information architecture": 8,
    "interaction design": 10,
    "wordpress": 8,
    "elementor": 5,
    "vue": 6,
    "svelte": 6,
    "graphql": 5,
    "rest api": 4,
    "seo": 10,
    "google analytics": 8,
    "social media": 8,
    "meta ads": 8,
    "google ads": 8,
    "content creation": 8,
}

EXCLUSION_KEYWORDS = [
    "data scientist", "machine learning", "deep learning",
    "devops", "sre", "infrastructure", "backend only",
    "sales", "account executive", "account manager",
    "copywriter", "content writer",
    "game designer",  # unless combined with UX
    "print designer",
    "hr manager", "recruiter",
    "financial analyst", "accountant",
    "physician", "nurse", "doctor",
    "mechanical engineer", "electrical engineer",
]

SPONSORSHIP_POSITIVE = [
    "visa sponsorship", "employment visa provided", "residence visa provided",
    "uae visa provided", "company provides visa", "work permit sponsorship",
    "sponsor visa", "will sponsor", "sponsorship available", "visa support",
    "work permit", "we sponsor",
]

SPONSORSHIP_NEGATIVE = [
    "no sponsorship", "no visa sponsorship", "no visa provided", "no visa",
    "will not sponsor", "not sponsor", "must be authorized",
    "must be eligible to work", "must have valid uae visa", "own visa",
    "citizen only", "permanent resident only",
    "us citizen", "uk citizen", "eu citizen",
    "right to work",
]

RELOCATION_NEGATIVE = [
    "no relocation", "relocation not provided", "relocation not offered",
    "without relocation",
]

FLIGHT_POSITIVE = [
    "flight ticket provided", "flight tickets provided", "annual flight",
    "return flight", "air ticket provided", "airfare covered",
    "flight allowance", "joining ticket", "repatriation ticket",
]

FLIGHT_NEGATIVE = [
    "no flight", "flights not covered", "airfare not included",
    "flight not provided",
]

ACCOMMODATION_POSITIVE = [
    "accommodation provided", "housing provided", "company accommodation",
    "housing allowance", "furnished accommodation", "hotel stay provided",
    "temporary accommodation", "accommodation covered",
]

ACCOMMODATION_NEGATIVE = [
    "no accommodation", "housing not provided", "accommodation not included",
    "accommodation not provided",
]

UAE_EMIRATES = [
    ("dubai", "Dubai, UAE"),
    ("abu dhabi", "Abu Dhabi, UAE"),
    ("sharjah", "Sharjah, UAE"),
    ("ajman", "Ajman, UAE"),
    ("ras al khaimah", "Ras Al Khaimah, UAE"),
    ("fujairah", "Fujairah, UAE"),
    ("umm al quwain", "Umm Al Quwain, UAE"),
]

REMOTE_WORLDWIDE_SIGNALS = [
    "remote worldwide", "work from anywhere", "fully remote",
    "anywhere in the world", "global remote", "remote global",
    "open to all countries", "all timezones",
    "100% remote",
]

REMOTE_RESTRICTED_SIGNALS = [
    "us only", "usa only", "uk only", "eu only",
    "europe only", "must be in", "based in",
    "north america only", "canada only",
    "australia only", "latam only",
]

RELOCATION_SIGNALS = [
    "relocation", "relocate", "relocation package",
    "relocation assistance", "relocation support",
]


@dataclass
class MatchConfig:
    min_title_score: int = 30
    skill_weight_multiplier: float = 1.0
    include_wordpress: bool = True
    include_related: bool = True
    max_posting_age_hours: float = 24.0
    enforce_age_filter: bool = True
    # Titles that immediately score very high
    high_value_titles: list[str] = field(default_factory=lambda: [
        "ux designer", "ui designer", "ui/ux", "product designer",
        "interaction designer", "design engineer", "web designer",
    ])


class JobMatcher:
    """
    Transparent rule-based matcher.
    Enforces the strict 24-hour UTC posting age rule centrally across all sources,
    and returns a score 0–100 with human-readable reasons.
    """

    def __init__(self, config: Optional[MatchConfig] = None):
        self.config = config or MatchConfig()

    def evaluate_posting_age(
        self, job: JobListing, now: Optional[datetime] = None
    ) -> tuple[bool, str]:
        """
        Verify that the job's original publication timestamp is reliable and within
        [0, max_posting_age_hours] in UTC.

        Updates job.age_hours, job.age_filter_passed, and job.exclusion_reason.
        """
        now_utc = to_utc(now) if now is not None else datetime.now(timezone.utc)
        if now_utc is None:
            now_utc = now.replace(tzinfo=timezone.utc)  # type: ignore[union-attr]

        effective_dt = job.posted_at
        using_verified_repost = False
        if effective_dt is None:
            if job.updated_at is not None and job.is_repost:
                effective_dt = job.updated_at
                using_verified_repost = True
            elif job.updated_at is not None:
                reason = (
                    "Excluded by age filter: source only provided last-updated timestamp, "
                    "not original posting date"
                )
                job.age_filter_passed = False
                job.exclusion_reason = reason
                return False, reason
            else:
                reason = "Excluded by age filter: missing or unreliable original posting date"
                job.age_filter_passed = False
                job.exclusion_reason = reason
                return False, reason

        if not using_verified_repost and not job.timestamp_reliable:
            reason = "Excluded by age filter: source posting timestamp is ambiguous or unreliable"
            job.age_filter_passed = False
            job.exclusion_reason = reason
            return False, reason

        posted_utc = to_utc(effective_dt)
        if posted_utc is None:
            reason = (
                "Excluded by age filter: original posting timestamp lacks timezone "
                "(cannot verify UTC age)"
            )
            job.age_filter_passed = False
            job.exclusion_reason = reason
            return False, reason

        age_seconds = (now_utc - posted_utc).total_seconds()
        age_hours = age_seconds / 3600.0
        job.age_hours = round(age_hours, 2)

        if age_seconds < 0:
            reason = (
                f"Excluded by age filter: posting timestamp is in the future "
                f"({age_hours:.2f}h, unreliable)"
            )
            job.age_filter_passed = False
            job.exclusion_reason = reason
            return False, reason

        max_hours = self.config.max_posting_age_hours
        if age_hours > max_hours:
            reason = (
                f"Excluded by age filter: posted {age_hours:.1f}h ago "
                f"(exceeds {max_hours:g}h limit)"
            )
            job.age_filter_passed = False
            job.exclusion_reason = reason
            return False, reason

        job.age_filter_passed = True
        job.exclusion_reason = ""
        return True, f"Posted {age_hours:.1f}h ago (within {max_hours:g}h UTC window)"

    def match(self, job: JobListing, now: Optional[datetime] = None) -> JobListing:
        """
        Score and categorize a job, enforcing the strict posting-age filter centrally.
        Mutates job in place and returns it.
        """
        if self.config.enforce_age_filter:
            age_ok, age_reason = self.evaluate_posting_age(job, now=now)
            if not age_ok:
                job.match_score = 0
                job.match_reasons = [age_reason]
                job.match_category = MatchCategory.IRRELEVANT
                return job

        title_lower = job.title.lower()
        desc_lower = (job.description or "").lower()
        combined = f"{title_lower} {desc_lower}"

        reasons: list[str] = []
        score = 0
        category = MatchCategory.IRRELEVANT

        # --- Exclusions first ---
        for excl in EXCLUSION_KEYWORDS:
            if excl in title_lower:
                # Exception: "game designer" in title but also "ux" → not excluded
                if excl == "game designer" and "ux" in combined:
                    continue
                reason = f"Excluded: title contains '{excl}'"
                job.match_score = 0
                job.exclusion_reason = reason
                job.match_reasons = [reason]
                job.match_category = MatchCategory.IRRELEVANT
                return job

        # --- Title scoring ---
        title_score, title_reasons, detected_category = self._score_title(title_lower)
        score += title_score
        reasons.extend(title_reasons)
        if detected_category != MatchCategory.IRRELEVANT:
            category = detected_category

        # --- Skill scoring (from description) ---
        skill_score, skill_reasons = self._score_skills(combined)
        score += min(skill_score, 35)  # cap skill bonus
        reasons.extend(skill_reasons)

        # --- Determine remote type, benefits & UAE location ---
        job.remote_type = self._detect_remote(combined, job.location)
        job.work_location = self._detect_work_location(job.location, combined) or job.location

        job.visa_sponsorship = self._detect_visa_benefit(combined)
        if job.visa_sponsorship == BenefitStatus.CONFIRMED:
            job.sponsorship = SponsorshipStatus.SPONSORED
        elif job.visa_sponsorship == BenefitStatus.UNAVAILABLE:
            job.sponsorship = SponsorshipStatus.NOT_SPONSORED
        else:
            job.sponsorship = SponsorshipStatus.UNKNOWN

        job.relocation_support = self._detect_relocation_benefit(combined)
        job.relocation_offered = job.relocation_support == BenefitStatus.CONFIRMED
        job.flight_covered = self._detect_benefit(combined, FLIGHT_POSITIVE, FLIGHT_NEGATIVE)
        job.accommodation_covered = self._detect_benefit(
            combined, ACCOMMODATION_POSITIVE, ACCOMMODATION_NEGATIVE
        )

        # --- Seniority extraction ---
        job.seniority = self._extract_seniority(title_lower + " " + desc_lower[:500])

        # --- Eligibility & benefit priority bonuses ---
        if job.remote_type == RemoteType.WORLDWIDE:
            score += 10
            reasons.append("Remote worldwide — eligible from Ethiopia")
        elif job.remote_type == RemoteType.RESTRICTED:
            if not any(c in combined for c in ["ethiopia", "africa", "worldwide", "uae", "dubai", "abu dhabi"]):
                score = max(0, score - 10)
                reasons.append("Remote restricted — may not include Ethiopia")

        if job.visa_sponsorship == BenefitStatus.CONFIRMED:
            score += 15
            reasons.append("Visa sponsorship confirmed")
        if job.relocation_support == BenefitStatus.CONFIRMED:
            score += 8
            reasons.append("Relocation support confirmed")
        if job.flight_covered == BenefitStatus.CONFIRMED:
            score += 5
            reasons.append("Flight ticket covered")
        if job.accommodation_covered == BenefitStatus.CONFIRMED:
            score += 5
            reasons.append("Accommodation covered")

        # --- Clamp ---
        score = max(0, min(100, score))
        job.match_score = score
        job.match_reasons = reasons[:8]  # keep top 8
        job.match_category = category if score >= self.config.min_title_score else MatchCategory.IRRELEVANT
        return job

    def _score_title(self, title: str) -> tuple[int, list[str], MatchCategory]:
        reasons = []
        score = 0
        category = MatchCategory.IRRELEVANT

        # High-value design titles
        for kw in DESIGN_TITLE_KEYWORDS:
            if kw in title:
                score = 60
                reasons.append(f"Title matches design role: '{kw}'")
                category = MatchCategory.DESIGN
                break

        # WordPress
        if category == MatchCategory.IRRELEVANT:
            for kw in WORDPRESS_TITLE_KEYWORDS:
                if kw in title:
                    score = 55
                    reasons.append(f"Title matches WordPress role: '{kw}'")
                    category = MatchCategory.WORDPRESS
                    break

        # Frontend
        if category == MatchCategory.IRRELEVANT:
            for kw in FRONTEND_TITLE_KEYWORDS:
                if kw in title:
                    score = 55
                    reasons.append(f"Title matches frontend role: '{kw}'")
                    category = MatchCategory.FRONTEND
                    break

        # Digital Marketing / SEO / Social Media / Content Creator
        if category == MatchCategory.IRRELEVANT:
            for kw in MARKETING_TITLE_KEYWORDS:
                if kw in title:
                    score = 55
                    reasons.append(f"Title matches digital marketing role: '{kw}'")
                    category = MatchCategory.MARKETING
                    break

        return score, reasons, category

    def _score_skills(self, text: str) -> tuple[int, list[str]]:
        total = 0
        reasons = []
        for skill, weight in SKILL_KEYWORDS.items():
            if skill in text:
                adjusted = int(weight * self.config.skill_weight_multiplier)
                total += adjusted
                reasons.append(f"Skill: {skill} (+{adjusted})")
                if len(reasons) >= 5:  # limit verbose output
                    break
        return total, reasons

    def _detect_remote(self, text: str, location: str) -> RemoteType:
        combined = f"{text} {location}".lower()
        for signal in REMOTE_WORLDWIDE_SIGNALS:
            if signal in combined:
                return RemoteType.WORLDWIDE
        # Check restricted
        for signal in REMOTE_RESTRICTED_SIGNALS:
            if signal in combined:
                return RemoteType.RESTRICTED
        if "remote" in combined:
            return RemoteType.RESTRICTED  # Remote but unclear scope → restricted
        if any(x in combined for x in ["hybrid", "flexible"]):
            return RemoteType.HYBRID
        if "onsite" in combined or "on-site" in combined or "in office" in combined:
            return RemoteType.ONSITE
        return RemoteType.UNKNOWN

    def _detect_sponsorship(self, text: str) -> SponsorshipStatus:
        status = self._detect_visa_benefit(text)
        if status == BenefitStatus.CONFIRMED:
            return SponsorshipStatus.SPONSORED
        if status == BenefitStatus.UNAVAILABLE:
            return SponsorshipStatus.NOT_SPONSORED
        return SponsorshipStatus.UNKNOWN

    def _detect_benefit(
        self, text: str, positive: list[str], negative: list[str]
    ) -> BenefitStatus:
        for phrase in negative:
            if phrase in text:
                return BenefitStatus.UNAVAILABLE
        for phrase in positive:
            if phrase in text:
                return BenefitStatus.CONFIRMED
        return BenefitStatus.NOT_CONFIRMED

    def _detect_visa_benefit(self, text: str) -> BenefitStatus:
        # Check negative phrases first so "no visa sponsorship" never triggers "visa sponsorship"
        for phrase in SPONSORSHIP_NEGATIVE:
            if phrase in text:
                return BenefitStatus.UNAVAILABLE
        for phrase in SPONSORSHIP_POSITIVE:
            if phrase in text:
                return BenefitStatus.CONFIRMED
        return BenefitStatus.NOT_CONFIRMED

    def _detect_relocation_benefit(self, text: str) -> BenefitStatus:
        for phrase in RELOCATION_NEGATIVE:
            if phrase in text:
                return BenefitStatus.UNAVAILABLE
        for phrase in RELOCATION_SIGNALS:
            if phrase in text:
                return BenefitStatus.CONFIRMED
        return BenefitStatus.NOT_CONFIRMED

    def _detect_work_location(self, location: str, text: str) -> str:
        loc_lower = (location or "").lower()
        for token, canonical in UAE_EMIRATES:
            if token in loc_lower or token in text:
                return canonical
        if "united arab emirates" in loc_lower or re.search(r"\buae\b", loc_lower):
            return "UAE"
        return location or ""

    def _extract_seniority(self, text: str) -> str:
        if any(w in text for w in ["lead", "principal", "staff", "head of"]):
            return "lead"
        if any(w in text for w in ["senior", "sr.", "sr "]):
            return "senior"
        if any(w in text for w in ["mid-level", "mid level", "intermediate"]):
            return "mid"
        if any(w in text for w in ["junior", "jr.", "entry level", "entry-level", "graduate"]):
            return "junior"
        return ""
