"""
Rule-based job matching engine.
Transparent, configurable, no paid AI required.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

from backend.core.models import JobListing, MatchCategory, RemoteType, SponsorshipStatus

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword definitions
# ---------------------------------------------------------------------------

DESIGN_TITLE_KEYWORDS = [
    "ui/ux", "ui ux", "ux/ui", "ux designer", "ui designer",
    "product designer", "web designer", "interaction designer",
    "visual designer", "figma designer", "ux researcher",
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

SKILL_KEYWORDS = {
    "figma": 15,
    "sketch": 10,
    "adobe xd": 10,
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
}

EXCLUSION_KEYWORDS = [
    "data scientist", "machine learning", "deep learning",
    "devops", "sre", "infrastructure", "backend only",
    "sales", "account executive", "account manager",
    "marketing manager", "seo specialist",
    "copywriter", "content writer",
    "game designer",  # unless combined with UX
    "print designer",
    "hr manager", "recruiter",
    "financial analyst", "accountant",
    "physician", "nurse", "doctor",
    "mechanical engineer", "electrical engineer",
]

SPONSORSHIP_POSITIVE = [
    "visa sponsorship", "sponsor visa", "will sponsor",
    "sponsorship available", "visa support", "work permit",
    "relocation package", "relocation assistance",
    "we sponsor",
]

SPONSORSHIP_NEGATIVE = [
    "no sponsorship", "no visa", "must be authorized",
    "must be eligible to work", "no relocation",
    "citizen only", "permanent resident only",
    "us citizen", "uk citizen", "eu citizen",
    "right to work", "not sponsor",
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
    # Titles that immediately score very high
    high_value_titles: list[str] = field(default_factory=lambda: [
        "ux designer", "ui designer", "ui/ux", "product designer",
        "interaction designer", "design engineer", "web designer",
    ])


class JobMatcher:
    """
    Transparent rule-based matcher.
    Returns a score 0–100 and a list of human-readable reasons.
    """

    def __init__(self, config: Optional[MatchConfig] = None):
        self.config = config or MatchConfig()

    def match(self, job: JobListing) -> JobListing:
        """
        Score and categorize a job. Mutates job in place and returns it.
        """
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
                job.match_score = 0
                job.match_reasons = [f"Excluded: title contains '{excl}'"]
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

        # --- Determine remote type ---
        job.remote_type = self._detect_remote(combined, job.location)
        job.sponsorship = self._detect_sponsorship(combined)
        job.relocation_offered = any(s in combined for s in RELOCATION_SIGNALS)

        # --- Seniority extraction ---
        job.seniority = self._extract_seniority(title_lower + " " + desc_lower[:500])

        # --- Ethiopian eligibility bonus ---
        if job.remote_type == RemoteType.WORLDWIDE:
            score += 10
            reasons.append("Remote worldwide — eligible from Ethiopia")
        elif job.sponsorship == SponsorshipStatus.SPONSORED:
            score += 15
            reasons.append("Visa sponsorship explicitly mentioned")
        elif job.relocation_offered:
            score += 8
            reasons.append("Relocation package mentioned")
        elif job.remote_type == RemoteType.RESTRICTED:
            # Penalize restricted remote unless Ethiopia/Africa mentioned
            if not any(c in combined for c in ["ethiopia", "africa", "worldwide"]):
                score = max(0, score - 10)
                reasons.append("Remote restricted — may not include Ethiopia")

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
        for phrase in SPONSORSHIP_POSITIVE:
            if phrase in text:
                return SponsorshipStatus.SPONSORED
        for phrase in SPONSORSHIP_NEGATIVE:
            if phrase in text:
                return SponsorshipStatus.NOT_SPONSORED
        return SponsorshipStatus.UNKNOWN

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
