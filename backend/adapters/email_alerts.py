"""
Email Alert Adapter (LinkedIn & Indeed Job Alerts).
LinkedIn and Indeed heavily rate limit, block scrapers, and disallow unauthorized crawling.
As requested in the architecture specification, this adapter provides the supported,
compliant alternative: it processes structured job alerts forwarded or synced from
LinkedIn and Indeed (via Gmail search query or local alert mailbox).
"""
from __future__ import annotations

import base64
import json
import logging
import re
from typing import Optional
from bs4 import BeautifulSoup

from backend.adapters.base import BaseAdapter
from backend.core.models import JobListing, RemoteType

logger = logging.getLogger(__name__)


class EmailAlertsAdapter(BaseAdapter):
    """
    Scans configured Gmail inbox for automated job alert emails from:
    - LinkedIn Job Alerts (jobalerts-noreply@linkedin.com)
    - Indeed Job Alerts (alert@indeed.com)
    Extracts individual job listings with title, company, location, and apply link.
    """
    SOURCE_ID = "email_alerts"
    DISPLAY_NAME = "LinkedIn & Indeed Job Alerts"
    ENABLED = True

    def fetch(self) -> list[JobListing]:
        from backend.core.config import get_config
        config = get_config()

        if not config.has_gmail:
            self.logger.info("Gmail credentials not provided — email alerts adapter skipped")
            return []

        try:
            from backend.core.notifier import GmailNotifier
            notifier = GmailNotifier(
                credentials_json=config.gmail_credentials_json,
                token_json=config.gmail_token_json,
                sender_email=config.notification_email,
            )
            service = notifier.service

            # Query for recent unread job alert emails from LinkedIn / Indeed
            query = "from:(jobalerts-noreply@linkedin.com OR alert@indeed.com) newer_than:2d"
            res = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
            messages = res.get("messages", [])
            self.logger.info("Found %d job alert emails", len(messages))

            all_jobs = []
            for msg_meta in messages:
                msg_id = msg_meta["id"]
                msg_full = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
                html_body = self._extract_html_body(msg_full)
                if not html_body:
                    continue

                if "linkedin" in json.dumps(msg_full.get("payload", {}).get("headers", [])).lower():
                    jobs = self._parse_linkedin_email(html_body, msg_id)
                else:
                    jobs = self._parse_indeed_email(html_body, msg_id)

                all_jobs.extend(jobs)

            return all_jobs

        except Exception as exc:
            self.logger.warning("Email alert fetching failed: %s", exc)
            return []

    def _extract_html_body(self, msg: dict) -> str:
        payload = msg.get("payload", {})
        parts = [payload]
        while parts:
            part = parts.pop()
            if part.get("mimeType") == "text/html":
                data = part.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data.encode("ASCII")).decode("utf-8", errors="ignore")
            if "parts" in part:
                parts.extend(part["parts"])
        return ""

    def _parse_linkedin_email(self, html: str, msg_id: str) -> list[JobListing]:
        jobs = []
        soup = BeautifulSoup(html, "html.parser")
        # LinkedIn job alert emails structure cards inside tables with view job links
        links = soup.find_all("a", href=re.compile(r"linkedin\.com/comm/jobs/view|linkedin\.com/jobs/view"))

        for idx, a in enumerate(links):
            title = a.get_text(strip=True)
            if not title or len(title) < 3 or "view job" in title.lower():
                continue
            url = a.get("href", "")

            # Look up parent table or container for company and location text
            parent = a.find_parent("table") or a.find_parent("div")
            company = "Company via LinkedIn"
            location = "Remote / Listed on LinkedIn"
            if parent:
                text_lines = [line.strip() for line in parent.get_text().split("\n") if line.strip()]
                if len(text_lines) > 1:
                    company = text_lines[1]
                if len(text_lines) > 2:
                    location = text_lines[2]

            jobs.append(
                JobListing(
                    source="linkedin_alert",
                    source_id=f"li_{msg_id}_{idx}",
                    url=url,
                    title=title,
                    company=company,
                    location=location,
                    posted_at=None,
                    timestamp_reliable=False,
                    remote_type=RemoteType.UNKNOWN,
                )
            )

        return jobs

    def _parse_indeed_email(self, html: str, msg_id: str) -> list[JobListing]:
        jobs = []
        soup = BeautifulSoup(html, "html.parser")
        links = soup.find_all("a", href=re.compile(r"indeed\.com/rc/clk|indeed\.com/viewjob"))

        for idx, a in enumerate(links):
            title = a.get_text(strip=True)
            if not title or len(title) < 3:
                continue
            url = a.get("href", "")
            parent = a.find_parent("table") or a.find_parent("div")
            company = "Company via Indeed"
            location = "Remote / Listed on Indeed"
            if parent:
                text_lines = [line.strip() for line in parent.get_text().split("\n") if line.strip()]
                if len(text_lines) > 1:
                    company = text_lines[1]
                if len(text_lines) > 2:
                    location = text_lines[2]

            jobs.append(
                JobListing(
                    source="indeed_alert",
                    source_id=f"in_{msg_id}_{idx}",
                    url=url,
                    title=title,
                    company=company,
                    location=location,
                    posted_at=None,
                    timestamp_reliable=False,
                    remote_type=RemoteType.UNKNOWN,
                )
            )

        return jobs

