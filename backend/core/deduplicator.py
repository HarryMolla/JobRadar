"""
Deduplication logic.
Uses fingerprints stored in Supabase to prevent repeat notifications.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.core.models import JobListing
from backend.core.storage import Storage

logger = logging.getLogger(__name__)


class Deduplicator:
    """
    Checks whether a job has already been seen.
    Uses in-memory cache + Supabase for persistence.
    """

    def __init__(self, storage: Storage):
        self.storage = storage
        self._seen: set[str] = set()
        self._loaded = False

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            try:
                known = self.storage.get_known_fingerprints()
                self._seen.update(known)
                self._loaded = True
                logger.info("Deduplicator loaded %d known fingerprints", len(self._seen))
            except Exception as exc:
                logger.error("Failed to load fingerprints from storage: %s", exc)
                self._loaded = True  # Avoid retry storm

    def is_new(self, job: JobListing) -> bool:
        """Return True if this job has never been stored."""
        self._ensure_loaded()
        return job.fingerprint not in self._seen

    def mark_seen(self, job: JobListing) -> None:
        self._seen.add(job.fingerprint)

    def filter_new(self, jobs: list[JobListing]) -> list[JobListing]:
        """
        Return only jobs not previously seen.
        Marks filtered jobs as seen in memory (storage commit happens separately).
        """
        new_jobs = []
        seen_in_batch: set[str] = set()
        for job in jobs:
            fp = job.fingerprint
            if fp not in self._seen and fp not in seen_in_batch:
                new_jobs.append(job)
                seen_in_batch.add(fp)
        return new_jobs
