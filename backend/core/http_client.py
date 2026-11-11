"""
Shared HTTP client with retry logic, rate limiting, and robots.txt checking.
"""
from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "JobRadar-Bot/1.0 (personal job monitoring tool; "
        "https://github.com/your-username/jobradar; "
        "contact: your-email@gmail.com)"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

# Cache robots.txt and optional per-run GET responses to reduce duplicate requests
_robots_cache: dict[str, Optional[RobotFileParser]] = {}
_response_cache: dict[str, requests.Response] = {}


class PermanentHTTPError(requests.HTTPError):
    """HTTP 4xx client error (e.g. 403/404) that should not be retried."""


def clear_cache() -> None:
    """Clear the per-run HTTP GET response cache."""
    _response_cache.clear()


def _get_robots(domain: str, timeout: int = 10) -> Optional[RobotFileParser]:
    if domain in _robots_cache:
        return _robots_cache[domain]
    try:
        rp = RobotFileParser()
        rp.set_url(f"https://{domain}/robots.txt")
        rp.read()
        _robots_cache[domain] = rp
        return rp
    except Exception as exc:
        logger.debug("Could not fetch robots.txt for %s: %s", domain, exc)
        _robots_cache[domain] = None
        return None


def is_allowed(url: str, user_agent: str = "JobRadar-Bot") -> bool:
    """Return True if robots.txt allows crawling this URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        rp = _get_robots(domain)
        if rp is None:
            return True  # Cannot check → allow (permissive)
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True  # On error, allow


class RateLimiter:
    """Simple per-domain rate limiter."""

    def __init__(self, default_delay: float = 2.0):
        self._last_request: dict[str, float] = {}
        self.default_delay = default_delay

    def wait(self, domain: str, delay: Optional[float] = None) -> None:
        d = delay if delay is not None else self.default_delay
        last = self._last_request.get(domain, 0)
        elapsed = time.monotonic() - last
        if elapsed < d:
            time.sleep(d - elapsed)
        self._last_request[domain] = time.monotonic()


_rate_limiter = RateLimiter()


def get(
    url: str,
    headers: Optional[dict] = None,
    params: Optional[dict] = None,
    timeout: int = 30,
    delay: Optional[float] = None,
    check_robots: bool = True,
    session: Optional[requests.Session] = None,
    use_cache: bool = False,
) -> requests.Response:
    """
    HTTP GET with rate limiting, robots.txt checking, caching, and retry.
    Raises requests.HTTPError on 5xx / 429 after retries, PermanentHTTPError on 4xx.
    Raises PermissionError if robots.txt disallows.
    """
    cache_key = f"{url}::{sorted((params or {}).items())}"
    if use_cache and cache_key in _response_cache:
        return _response_cache[cache_key]

    if check_robots and not is_allowed(url):
        raise PermissionError(f"robots.txt disallows: {url}")

    parsed = urlparse(url)
    domain = parsed.netloc
    _rate_limiter.wait(domain, delay)

    merged_headers = {**DEFAULT_HEADERS, **(headers or {})}
    client = session or requests.Session()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(
            (requests.ConnectionError, requests.Timeout, requests.HTTPError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _do_get() -> requests.Response:
        resp = client.get(url, headers=merged_headers, params=params, timeout=timeout)
        # Retry on 429 / 5xx; fail fast on permanent 4xx (403/404) without wasting Actions minutes
        if resp.status_code == 429:
            retry_after = min(int(resp.headers.get("Retry-After", "60")), 60)
            logger.warning("Rate limited by %s — sleeping %ds", domain, retry_after)
            time.sleep(retry_after)
            raise requests.HTTPError(response=resp)
        if resp.status_code >= 500:
            raise requests.HTTPError(response=resp)
        return resp

    resp = _do_get()
    if 400 <= resp.status_code < 500:
        raise PermanentHTTPError(f"HTTP {resp.status_code} for {url}", response=resp)
    resp.raise_for_status()
    if use_cache:
        _response_cache[cache_key] = resp
    return resp


def get_json(url: str, **kwargs) -> dict:
    resp = get(url, **kwargs)
    return resp.json()
