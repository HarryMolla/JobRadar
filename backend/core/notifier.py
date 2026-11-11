"""
Notification dispatcher.
Supports Gmail (primary) and Telegram (optional fallback).
"""
from __future__ import annotations

import base64
import json
import logging
import os
import pickle
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gmail notifier
# ---------------------------------------------------------------------------

class GmailNotifier:
    """
    Sends email via Gmail API using OAuth 2.0.
    Credentials are stored in environment variables — never in source code.

    Setup instructions:
    1. Go to https://console.cloud.google.com/
    2. Create a project → Enable Gmail API
    3. Create OAuth 2.0 credentials (Desktop app)
    4. Download credentials.json
    5. Run: python scripts/gmail_auth.py
    6. Copy token.json content to GMAIL_TOKEN_JSON secret
    7. Copy credentials.json content to GMAIL_CREDENTIALS_JSON secret
    """

    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    def __init__(self, credentials_json: str, token_json: str, sender_email: str):
        self.sender_email = sender_email
        self._credentials_json = credentials_json
        self._token_json = token_json
        self._service = None

    def _build_service(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_data = json.loads(self._token_json)

        # Fallback to credentials_json if client_id or client_secret are not inside token_json
        client_id = token_data.get("client_id")
        client_secret = token_data.get("client_secret")
        if not client_id or not client_secret:
            try:
                creds_raw = json.loads(self._credentials_json)
                app_info = creds_raw.get("installed") or creds_raw.get("web") or {}
                client_id = client_id or app_info.get("client_id")
                client_secret = client_secret or app_info.get("client_secret")
            except Exception as e:
                logger.debug("Could not parse client_id from credentials_json: %s", e)

        creds = Credentials(
            token=token_data.get("token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=client_id,
            client_secret=client_secret,
            scopes=token_data.get("scopes", self.SCOPES),
        )
        # Refresh if expired
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Gmail token refreshed successfully")
            except Exception as exc:
                logger.error("Failed to refresh Gmail token: %s", exc)
                raise

        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    @property
    def service(self):
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def send_digest(
        self,
        jobs: list[dict],
        to_email: str,
        subject: Optional[str] = None,
    ) -> bool:
        """Send a digest email with multiple job listings."""
        if not jobs:
            logger.info("No jobs to notify about")
            return True

        if subject is None:
            subject = f"JobRadar — {len(jobs)} new job{'s' if len(jobs) > 1 else ''} found"

        html_body = self._build_html(jobs)
        text_body = self._build_text(jobs)

        try:
            message = self._create_message(to_email, subject, html_body, text_body)
            self.service.users().messages().send(
                userId="me", body=message
            ).execute()
            logger.info("Digest email sent to %s (%d jobs)", to_email, len(jobs))
            return True
        except Exception as exc:
            logger.error("Failed to send Gmail digest: %s", exc)
            return False

    def _create_message(
        self, to: str, subject: str, html: str, text: str
    ) -> dict:
        msg = MIMEMultipart("alternative")
        msg["to"] = to
        msg["from"] = self.sender_email
        msg["subject"] = subject
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        return {"raw": raw}

    def _build_html(self, jobs: list[dict]) -> str:
        rows = []
        for job in jobs:
            score = job.get("match_score", 0)
            reasons = "; ".join(job.get("match_reasons", [])[:3])
            location = job.get("work_location") or job.get("location", "?")
            source_name = job.get("source_name") or job.get("source", "?")
            apply_url = job.get("source_job_url") or job.get("url", "#")
            visa = job.get("visa_sponsorship", "not_confirmed")
            reloc = job.get("relocation_support", "not_confirmed")
            flight = job.get("flight_covered", "not_confirmed")
            accom = job.get("accommodation_covered", "not_confirmed")
            age_label = f" ({job['age_hours']}h ago)" if job.get("age_hours") is not None else ""
            salary = ""
            if job.get("salary_min"):
                salary = f"{job.get('salary_currency','')} {job['salary_min']:,}"
                if job.get("salary_max"):
                    salary += f" – {job['salary_max']:,}"

            benefit_lines = []
            if visa == "confirmed" or job.get("sponsorship") == "sponsored":
                benefit_lines.append('<p style="color:#15803d;margin:0 0 4px 0;font-size:12px;">✓ Visa sponsorship confirmed</p>')
            elif visa == "unavailable" or job.get("sponsorship") == "not_sponsored":
                benefit_lines.append('<p style="color:#b91c1c;margin:0 0 4px 0;font-size:12px;">✕ Visa sponsorship unavailable</p>')
            else:
                benefit_lines.append('<p style="color:#6b7280;margin:0 0 4px 0;font-size:12px;">? Visa sponsorship not confirmed</p>')
            if reloc == "confirmed" or job.get("relocation_offered"):
                benefit_lines.append('<p style="color:#1d4ed8;margin:0 0 4px 0;font-size:12px;">📦 Relocation support confirmed</p>')
            if flight == "confirmed":
                benefit_lines.append('<p style="color:#0369a1;margin:0 0 4px 0;font-size:12px;">✈️ Flight ticket covered</p>')
            if accom == "confirmed":
                benefit_lines.append('<p style="color:#0369a1;margin:0 0 4px 0;font-size:12px;">🏠 Accommodation covered</p>')

            rows.append(f"""
<div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin-bottom:12px;font-family:sans-serif;">
  <h3 style="margin:0 0 4px 0;color:#1a1a2e;">
    <a href="{apply_url}" style="color:#1a1a2e;text-decoration:none;">
      {job.get('title','Unknown')}
    </a>
  </h3>
  <p style="margin:0 0 8px 0;color:#555;">
    {job.get('company','?')} · {location}
    {f' · {job.get("remote_type","").replace("_"," ").title()}' if job.get('remote_type') else ''}
  </p>
  {'<p style="color:#27ae60;margin:0 0 4px 0;">💰 ' + salary + '</p>' if salary else ''}
  <p style="color:#e67e22;margin:0 0 4px 0;font-size:13px;">Match score: {score}/100</p>
  <p style="color:#666;margin:0 0 8px 0;font-size:12px;">Why: {reasons}</p>
  {''.join(benefit_lines)}
  <a href="{apply_url}" style="display:inline-block;background:#1a1a2e;color:white;padding:8px 16px;border-radius:4px;text-decoration:none;font-size:14px;margin-top:4px;">
    Apply Now →
  </a>
  <p style="color:#999;font-size:11px;margin:8px 0 0 0;">
    Source: {source_name} · First seen: {job.get('detected_at','?')[:16]}
    {' · Posted: ' + str(job.get('posted_at'))[:16] + age_label if job.get('posted_at') else ''}
  </p>
</div>""")
        return f"""
<!DOCTYPE html><html><body style="background:#f5f5f5;padding:20px;">
<h2 style="font-family:sans-serif;color:#1a1a2e;">
  🎯 JobRadar — {len(jobs)} New Job{'s' if len(jobs)>1 else ''} Found
</h2>
<p style="font-family:sans-serif;color:#666;">
  These jobs matched your profile. Review and apply early!
</p>
{''.join(rows)}
<p style="font-family:sans-serif;color:#999;font-size:12px;margin-top:20px;">
  JobRadar — Personal Job Monitor · Unsubscribe by disabling notifications in settings
</p>
</body></html>"""

    def _build_text(self, jobs: list[dict]) -> str:
        lines = [f"JobRadar — {len(jobs)} new job(s) found\n", "=" * 50]
        for job in jobs:
            lines.append(f"\n{job.get('title','?')} at {job.get('company','?')}")
            lines.append(f"Location: {job.get('location','?')}")
            lines.append(f"Score: {job.get('match_score',0)}/100")
            lines.append(f"Why: {'; '.join(job.get('match_reasons',[])[:3])}")
            lines.append(f"Apply: {job.get('url','')}")
            lines.append("-" * 40)
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Telegram notifier (optional backup)
# ---------------------------------------------------------------------------

class TelegramNotifier:
    """
    Sends Telegram messages via Bot API.
    Free, no OAuth needed. Good backup for Gmail.

    Setup:
    1. Talk to @BotFather on Telegram → create bot → get token
    2. Send any message to your bot
    3. GET https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat_id
    4. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in secrets
    """

    BASE = "https://api.telegram.org"

    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id

    def send_digest(self, jobs: list[dict]) -> bool:
        import requests as req
        if not jobs:
            return True
        messages = []
        for job in jobs[:5]:  # Telegram has message length limits
            msg = (
                f"🎯 *{job.get('title','?')}* at _{job.get('company','?')}_\n"
                f"📍 {job.get('location','?')}\n"
                f"⭐ Score: {job.get('match_score',0)}/100\n"
                f"🔗 [Apply]({job.get('url','')})"
            )
            messages.append(msg)

        combined = "\n\n".join(messages)
        if len(jobs) > 5:
            combined += f"\n\n...and {len(jobs)-5} more. Check the extension."

        try:
            resp = req.post(
                f"{self.BASE}/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": combined,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return True
        except Exception as exc:
            logger.error("Telegram send failed: %s", exc)
            return False
