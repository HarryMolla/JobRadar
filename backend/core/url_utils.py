"""
Job URL validation and resolution utilities.

Ensures every JobListing prefers a valid direct application URL (`apply_url`)
or exact individual job-detail URL (`source_job_url`), and rejects generic
careers/search/list URLs rather than sending users to browse pages.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

_GENERIC_EXACT_PATHS = {
    "",
    "apply",
    "jobs",
    "job",
    "careers",
    "career",
    "vacancies",
    "openings",
    "positions",
    "open-positions",
    "work-with-us",
    "join-us",
    "job-search",
    "jobs/search",
    "jobs/api",
    "search",
    "search-and-apply",
    "remote-jobs",
    "remote-design-jobs",
    "en/uae/jobs",
    "uae/jobs",
    "srp/results",
    "j",
    "o",
    "job-detail",
    "companies",
    "employment",
}

_JOB_ID_QUERY_PARAMS = {
    "id",
    "jobid",
    "job_id",
    "gh_jid",
    "jk",
    "vjk",
    "postingid",
    "requisitionid",
    "offerid",
    "vacancyid",
    "reqid",
    "rid",
}

_SEARCH_QUERY_PARAMS = {
    "q",
    "query",
    "keywords",
    "keyword",
    "search",
    "searchtext",
    "pos_ref",
    "xz",
    "locations",
    "location",
}


def clean_job_url(raw_url: str | None) -> str:
    """Validate scheme and host of a candidate URL, returning stripped URL or ''."""
    if not raw_url or not isinstance(raw_url, str):
        return ""
    candidate = raw_url.strip()
    if not candidate or candidate.startswith("#"):
        return ""
    try:
        parsed = urlparse(candidate)
    except Exception:
        return ""
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return ""
    return candidate


def is_generic_listing_url(url: str) -> bool:
    """
    Return True when a URL points to a homepage, generic careers portal,
    search results page, or incomplete path lacking a job identifier.
    """
    cleaned = clean_job_url(url)
    if not cleaned:
        return True

    parsed = urlparse(cleaned)
    norm_path = parsed.path.strip("/").lower()
    query_keys = {k.lower() for k, v in parse_qsl(parsed.query) if v.strip()}

    # If URL explicitly carries a job-ID query parameter, it targets a specific job
    if query_keys & _JOB_ID_QUERY_PARAMS:
        return False

    # Bare homepage, known board/search path, or trailing empty job prefix
    if norm_path in _GENERIC_EXACT_PATHS:
        return True

    if any(norm_path.endswith(suffix) for suffix in ("/jobs", "/careers", "/job-search", "/search-and-apply", "/j", "/job", "/o")):
        return True

    # Search result pages (?q=..., ?keywords=..., ?query=...) without specific job ID
    if query_keys & _SEARCH_QUERY_PARAMS and not any(
        seg in norm_path for seg in ("/job/", "/jobs/", "/job-detail/", "/viewjob", "/companies/")
    ):
        return True

    return False


def is_valid_job_url(url: str | None) -> bool:
    """Return True if URL is a valid http(s) URL targeting a specific job."""
    cleaned = clean_job_url(url)
    return bool(cleaned) and not is_generic_listing_url(cleaned)


def resolve_job_urls(
    apply_url: str | None = "",
    detail_url: str | None = "",
    fallback_url: str | None = "",
) -> tuple[str, str, str]:
    """
    Normalize and prioritize job URLs without inventing or guessing links.

    Returns:
        (primary_url, valid_apply_url, valid_detail_url)
        - `primary_url` prefers `apply_url` when valid, then `detail_url`, then `fallback_url`.
        - Generic careers/search/homepage URLs are rejected as `''`.
    """
    valid_apply = clean_job_url(apply_url) if is_valid_job_url(apply_url) else ""
    valid_detail = clean_job_url(detail_url) if is_valid_job_url(detail_url) else ""
    valid_fallback = clean_job_url(fallback_url) if is_valid_job_url(fallback_url) else ""

    if not valid_detail and valid_fallback and valid_fallback != valid_apply:
        valid_detail = valid_fallback

    primary = valid_apply or valid_detail or valid_fallback
    return primary, valid_apply, valid_detail
