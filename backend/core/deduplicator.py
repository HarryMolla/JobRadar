"""
Deduplication logic.
Uses fingerprints, canonical URLs, and cross-source title+company signatures
stored in repository state (data/job_state.json) to prevent repeat notifications.
"""
from __future__ import annotations

import logging
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.core.models import JobListing
from backend.core.storage import Storage

logger = logging.getLogger(__name__)


def normalize_job_url(raw_url: str) -> str:
    """Normalize a job URL by stripping tracking query params and trailing slashes."""
    if not raw_url:
        return ""
    try:
        parsed = urlparse(raw_url.strip())
        kept_params = [
            (k, v)
            for k, v in parse_qsl(parsed.query)
            if not k.lower().startswith("utm_")
            and k.lower() not in {"ref", "source", "jobsource", "trk"}
        ]
        clean_path = parsed.path.rstrip("/") or "/"
        return urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            "",
            urlencode(kept_params),
            "",
        ))
    except Exception:
        return raw_url.strip().lower().rstrip("/")


def normalize_text_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


class Deduplicator:
    """
    Checks whether a job has already been seen, including cross-source duplicates.
    Uses in-memory cache + repository Storage for persistence.
    """

    def __init__(self, storage: Storage):
        self.storage = storage
        self._seen: set[str] = set()
        self._seen_urls: set[str] = set()
        # Maps (normalized_title, normalized_company) -> source that first owned it
        self._seen_signatures: dict[tuple[str, str], str] = {}
        self._loaded = False

    def _signature(self, job: JobListing) -> tuple[str, str] | None:
        title_k = normalize_text_key(job.title)
        comp_k = normalize_text_key(job.company)
        if title_k and comp_k:
            return (title_k, comp_k)
        return None

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            try:
                known = self.storage.get_known_fingerprints()
                self._seen.update(known)
                raw_data = getattr(self.storage, "_data", None)
                if isinstance(raw_data, dict) and isinstance(raw_data.get("jobs"), dict):
                    for row in raw_data["jobs"].values():
                        if not isinstance(row, dict):
                            continue
                        norm_u = normalize_job_url(row.get("source_job_url") or row.get("url", ""))
                        if norm_u:
                            self._seen_urls.add(norm_u)
                        title_k = normalize_text_key(row.get("title", ""))
                        comp_k = normalize_text_key(row.get("company", ""))
                        if title_k and comp_k:
                            self._seen_signatures.setdefault((title_k, comp_k), row.get("source", ""))
                self._loaded = True
                logger.info("Deduplicator loaded %d known fingerprints", len(self._seen))
            except Exception as exc:
                logger.error("Failed to load fingerprints from storage: %s", exc)
                self._loaded = True  # Avoid retry storm

    def is_new(self, job: JobListing) -> bool:
        """Return True if this job has never been stored (by fingerprint, URL, or cross-source match)."""
        self._ensure_loaded()
        if job.fingerprint in self._seen:
            return False
        norm_u = normalize_job_url(job.source_job_url or job.url)
        if norm_u and norm_u in self._seen_urls:
            return False
        sig = self._signature(job)
        if sig and sig in self._seen_signatures and self._seen_signatures[sig] != job.source:
            return False
        return True

    def mark_seen(self, job: JobListing) -> None:
        self._seen.add(job.fingerprint)
        norm_u = normalize_job_url(job.source_job_url or job.url)
        if norm_u:
            self._seen_urls.add(norm_u)
        sig = self._signature(job)
        if sig:
            self._seen_signatures.setdefault(sig, job.source)

    def filter_new(self, jobs: list[JobListing]) -> list[JobListing]:
        """
        Return only jobs not previously seen.
        Deduplicates within batch and across sources without marking storage until persisted.
        """
        self._ensure_loaded()
        new_jobs = []
        seen_in_batch: set[str] = set()
        urls_in_batch: set[str] = set()
        sigs_in_batch: dict[tuple[str, str], str] = {}

        for job in jobs:
            fp = job.fingerprint
            if fp in self._seen or fp in seen_in_batch:
                continue
            norm_u = normalize_job_url(job.source_job_url or job.url)
            if norm_u and (norm_u in self._seen_urls or norm_u in urls_in_batch):
                continue
            sig = self._signature(job)
            if sig:
                existing_src = self._seen_signatures.get(sig) or sigs_in_batch.get(sig)
                if existing_src and existing_src != job.source:
                    continue

            new_jobs.append(job)
            seen_in_batch.add(fp)
            if norm_u:
                urls_in_batch.add(norm_u)
            if sig:
                sigs_in_batch.setdefault(sig, job.source)
        return new_jobs
