"""
UTC timestamp parsing and validation utilities.
Ensures consistent UTC age calculations across all sources and prevents
timezone bugs, naive datetime errors, or mistaking updates/ambiguous dates
for fresh postings.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from dateutil import parser as dateutil_parser

# Matches pure calendar dates without a time component (e.g., "2026-11-11" or "11/11/2026")
_DATE_ONLY_RE = re.compile(
    r"^\s*(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\s*$"
)


def parse_utc_timestamp(
    value: Any,
    assume_utc_if_naive: bool = False,
) -> tuple[Optional[datetime], str, bool]:
    """
    Parse a source timestamp into a UTC-aware datetime and a reliability flag.

    Returns:
        (dt_utc, raw_str, is_reliable)
        - dt_utc: UTC-aware datetime if reliably parsed, else None (or naive dt if unreliable).
        - raw_str: Original string representation for debugging/logging.
        - is_reliable: True only if the timestamp has an unambiguous date, time, and timezone
                       (or assume_utc_if_naive=True for documented-UTC APIs).
    """
    if value is None:
        return None, "", False

    if isinstance(value, datetime):
        raw_str = value.isoformat()
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc), raw_str, True
        if assume_utc_if_naive:
            return value.replace(tzinfo=timezone.utc), raw_str, True
        return None, raw_str, False

    if isinstance(value, (int, float)):
        raw_str = str(value)
        try:
            # Handle millisecond epoch timestamps
            ts = float(value)
            if ts > 1e11:
                ts /= 1000.0
            if ts <= 0:
                return None, raw_str, False
            return datetime.fromtimestamp(ts, tz=timezone.utc), raw_str, True
        except (ValueError, OverflowError, OSError):
            return None, raw_str, False

    raw_str = str(value).strip()
    if not raw_str:
        return None, "", False

    # Reject date-only strings (no time-of-day -> up to 24h + timezone ambiguity)
    if _DATE_ONLY_RE.match(raw_str):
        return None, raw_str, False

    # Reject relative/human phrases (e.g. "Posted Today", "2 days ago")
    lower = raw_str.lower()
    if any(word in lower for word in ("today", "yesterday", "ago", "recent", "just now")):
        return None, raw_str, False

    try:
        dt = dateutil_parser.parse(raw_str)
    except (ValueError, OverflowError, TypeError):
        return None, raw_str, False

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc), raw_str, True

    if assume_utc_if_naive:
        return dt.replace(tzinfo=timezone.utc), raw_str, True

    # Timezone missing and not guaranteed UTC -> ambiguous/unreliable
    return None, raw_str, False


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Convert an aware datetime to UTC. Returns None if dt is None or naive."""
    if dt is None or dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)

