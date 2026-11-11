"""
Catalog of UAE job sources and UAE search terms/locations.
Used by backend status reporting and synchronized with the Chrome extension UAE Sources UI.
"""
from __future__ import annotations

from typing import Optional

UAE_SEARCH_KEYWORDS: list[str] = [
    "visa sponsorship",
    "employment visa provided",
    "relocation assistance",
    "international candidates",
    "overseas applicants",
    "flight ticket provided",
    "accommodation provided",
    "work permit sponsorship",
    "UI UX Designer",
    "Product Designer",
    "Frontend Developer",
    "WordPress Developer",
    "Digital Marketing Specialist",
]

UAE_LOCATIONS: list[str] = [
    "Dubai",
    "Abu Dhabi",
    "Sharjah",
    "Ajman",
    "Ras Al Khaimah",
    "UAE",
]

UAE_SOURCE_CATALOG: list[dict] = [
    # --- General job boards ---
    {
        "id": "bayt",
        "name": "Bayt",
        "category": "general",
        "url": "https://www.bayt.com/en/uae/jobs/",
        "search_url": "https://www.bayt.com/en/uae/jobs/?filters%5Bjb_last_updated_date_id%5D%5B%5D=1&q={query}",
        "mode": "manual",
        "reason": "Cloudflare 403 anti-bot challenge; robots.txt disallows search query paths — manual search link provided.",
    },
    {
        "id": "indeed_uae",
        "name": "Indeed UAE",
        "category": "general",
        "url": "https://ae.indeed.com/",
        "search_url": "https://ae.indeed.com/jobs?q={query}&l={location}&fromage=1",
        "mode": "email_or_manual",
        "reason": "Cloudflare 403 protection on web search; supported via Gmail Indeed job alert parser or manual search.",
    },
    {
        "id": "dubizzle",
        "name": "Dubizzle Jobs",
        "category": "general",
        "url": "https://dubai.dubizzle.com/jobs/",
        "search_url": "https://dubai.dubizzle.com/jobs/?keywords={query}",
        "mode": "manual",
        "reason": "Dynamic JS/anti-bot shell without a public JobPosting feed — manual search link provided.",
    },
    {
        "id": "gulftalent",
        "name": "GulfTalent",
        "category": "general",
        "url": "https://www.gulftalent.com/uae/jobs",
        "search_url": "https://www.gulftalent.com/uae/jobs?pos_ref={query}",
        "mode": "manual",
        "reason": "Cloudflare 403 anti-bot protection — manual search link provided.",
    },
    {
        "id": "naukrigulf",
        "name": "Naukrigulf",
        "category": "general",
        "url": "https://www.naukrigulf.com/",
        "search_url": "https://www.naukrigulf.com/jobs-in-uae?xz={query}",
        "mode": "manual",
        "reason": "Endpoint unreachable/timed out for automated requests — manual search link provided.",
    },
    {
        "id": "linkedin_uae",
        "name": "LinkedIn Jobs UAE",
        "category": "general",
        "url": "https://www.linkedin.com/jobs/search/?location=United%20Arab%20Emirates",
        "search_url": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}%2C%20United%20Arab%20Emirates&f_TPR=r86400",
        "mode": "email_or_manual",
        "reason": "robots.txt prohibits automated scraping; supported via Gmail LinkedIn alerts or 24h manual search.",
    },
    {
        "id": "founditgulf",
        "name": "Foundit Gulf",
        "category": "general",
        "url": "https://www.founditgulf.com/",
        "search_url": "https://www.founditgulf.com/srp/results?query={query}&locations={location}",
        "mode": "manual",
        "reason": "HTTP 403 Akamai WAF block on site and robots.txt — manual search link provided.",
    },
    {
        "id": "glassdoor_uae",
        "name": "Glassdoor UAE",
        "category": "general",
        "url": "https://www.glassdoor.com/Job/united-arab-emirates-jobs-SRCH_IL.0,20_IN6.htm",
        "search_url": "https://www.glassdoor.com/Job/united-arab-emirates-jobs-SRCH_IL.0,20_IN6.htm?fromAge=1",
        "mode": "manual",
        "reason": "Cloudflare 403 anti-bot protection — manual search link provided.",
    },
    {
        "id": "laimoon",
        "name": "Laimoon",
        "category": "general",
        "url": "https://www.laimoon.com/",
        "search_url": "https://jobs.laimoon.com/uae/{query}",
        "mode": "manual",
        "reason": "Robots/feed host unreachable for automated fetch — manual search link provided.",
    },
    {
        "id": "gulfnews",
        "name": "Gulf News",
        "category": "general",
        "url": "https://gulfnews.com/",
        "search_url": "https://gulfnews.com/search?q={query}%20jobs",
        "mode": "manual",
        "reason": "General news portal without a structured JobPosting API/feed — manual search link provided.",
    },
    # --- Government recruitment portals ---
    {
        "id": "dubaicareers",
        "name": "Dubai Careers",
        "category": "government",
        "url": "https://dubaicareers.ae/",
        "search_url": "https://jobs.dubaicareers.ae/careersection/dubaicareers/jobsearch.ftl?lang=en",
        "mode": "manual",
        "reason": "Taleo portal requires interactive session/SSO; public REST search disabled — manual search link provided.",
    },
    {
        "id": "tamm",
        "name": "Abu Dhabi TAMM",
        "category": "government",
        "url": "https://www.tamm.abudhabi/",
        "search_url": "https://www.tamm.abudhabi/en/life-events/employment",
        "mode": "manual",
        "reason": "UAE PASS authenticated government portal / unreachable externally — manual search link provided.",
    },
    {
        "id": "fahr",
        "name": "UAE FAHR",
        "category": "government",
        "url": "https://www.fahr.gov.ae/",
        "search_url": "https://www.fahr.gov.ae/",
        "mode": "manual",
        "reason": "Federal HR portal requires UAE PASS / lacks public JobPosting feed — manual search link provided.",
    },
    {
        "id": "sharjahhr",
        "name": "Sharjah HR",
        "category": "government",
        "url": "https://www.sharjahhr.gov.ae/",
        "search_url": "https://www.sharjahhr.gov.ae/",
        "mode": "manual",
        "reason": "Government portal unreachable externally / no public JobPosting API — manual search link provided.",
    },
    # --- Specialist recruitment agencies ---
    {
        "id": "michaelpage_ae",
        "name": "Michael Page UAE",
        "category": "agency",
        "url": "https://www.michaelpage.ae/",
        "search_url": "https://www.michaelpage.ae/jobs/{query}",
        "mode": "manual",
        "reason": "Static search HTML lacks embedded job cards/timestamps — manual search link provided.",
    },
    {
        "id": "hays_uae",
        "name": "Hays UAE",
        "category": "agency",
        "url": "https://www.hays.ae/",
        "search_url": "https://www.hays.ae/job-search?q={query}&location={location}",
        "mode": "automated",
        "reason": "Public job search + JSON-LD parser (strictly excludes date-only listings under 24h rule).",
    },
    # --- Direct employer career pages ---
    {
        "id": "emirates",
        "name": "Emirates Group",
        "category": "employer",
        "url": "https://www.emiratesgroupcareers.com/",
        "search_url": "https://www.emiratesgroupcareers.com/search-and-apply/",
        "mode": "manual",
        "reason": "Delegates applications to Avature login; robots.txt disallows search query parameters — manual link provided.",
    },
    {
        "id": "sawatech",
        "name": "SawaTech",
        "category": "employer",
        "url": "https://www.sawatech.com/careers/",
        "search_url": "https://www.sawatech.com/careers/",
        "mode": "automated",
        "reason": "Permitted public RSS feed (/jobs/feed/) + JSON-LD JobPosting with verified UAE offset timestamp.",
    },
    {
        "id": "prism_digital",
        "name": "Prism Digital",
        "category": "employer",
        "url": "https://www.prism-me.com/careers",
        "search_url": "https://www.prism-me.com/careers",
        "mode": "automated",
        "reason": "Permitted Next.js __NEXT_DATA__ careers feed with verified UTC createdAt timestamps.",
    },
]


def build_uae_source_status(source_runs: Optional[list[dict]] = None) -> list[dict]:
    """Merge UAE source catalog with latest collector run results."""
    latest_by_source: dict[str, dict] = {}
    for run in source_runs or []:
        src = run.get("source")
        if src and src not in latest_by_source:
            latest_by_source[src] = run

    merged: list[dict] = []
    for entry in UAE_SOURCE_CATALOG:
        item = dict(entry)
        run = latest_by_source.get(entry["id"])
        # LinkedIn/Indeed alert modes map to email_alerts run status if present
        if not run and entry["id"] in ("linkedin_uae", "indeed_uae"):
            run = latest_by_source.get("email_alerts")
        if run:
            item["last_checked_at"] = run.get("checked_at")
            item["last_success"] = bool(run.get("success"))
            item["last_jobs_found"] = run.get("jobs_found", 0)
            item["last_error"] = run.get("error", "")
        else:
            item["last_checked_at"] = None
            item["last_success"] = None
            item["last_jobs_found"] = 0
            item["last_error"] = ""
        merged.append(item)
    return merged

