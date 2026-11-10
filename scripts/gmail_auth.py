"""
Gmail OAuth authorization script.
Run this locally ONCE to generate your OAuth token.
Then copy the token to GMAIL_TOKEN_JSON in GitHub Secrets.

Usage:
  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
  python scripts/gmail_auth.py

Prerequisites:
  1. Create a project at https://console.cloud.google.com/
  2. Enable the Gmail API
  3. Create OAuth 2.0 credentials (Desktop app type)
  4. Download credentials.json to this directory
"""
import json
import os
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
except ImportError:
    print("ERROR: Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")
    sys.exit(1)

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
CREDS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")


def main():
    if not CREDS_FILE.exists():
        print(f"ERROR: {CREDS_FILE} not found.")
        print("Download it from Google Cloud Console:")
        print("  Console → APIs & Services → Credentials → Download credentials.json")
        sys.exit(1)

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print(f"Token saved to {TOKEN_FILE}")

    print("\n✅ Gmail OAuth successful!")
    print(f"\nToken file: {TOKEN_FILE.absolute()}")
    print("\nNext steps:")
    print("1. Copy credentials.json content → GMAIL_CREDENTIALS_JSON secret in GitHub")
    print("2. Copy token.json content → GMAIL_TOKEN_JSON secret in GitHub")
    print(f"3. Set NOTIFICATION_EMAIL in GitHub Secrets to your Gmail address")
    print("\n⚠️  NEVER commit credentials.json or token.json to Git!")

    # Test send
    test = input("\nSend a test email? (y/N): ").strip().lower()
    if test == "y":
        import base64
        from email.mime.text import MIMEText
        from googleapiclient.discovery import build

        email_addr = input("Your Gmail address: ").strip()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        msg = MIMEText("JobRadar test email — Gmail API is working correctly!")
        msg["to"] = email_addr
        msg["from"] = email_addr
        msg["subject"] = "JobRadar — Gmail Test"
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        try:
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
            print("✅ Test email sent! Check your inbox.")
        except Exception as exc:
            print(f"❌ Failed: {exc}")


if __name__ == "__main__":
    main()
