"""
Persistent repository storage via data/job_state.json.
Eliminates Supabase and external database dependencies.
State is safely versioned, atomically written, and persisted in Git.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_STATE_PATH = Path("data/job_state.json")
LEGACY_FALLBACK_PATH = Path("jobs_fallback.json")


class Storage:
    """
    JSON-file-based persistent storage for JobRadar.
    Persists collector state, detected jobs, notification status, and source runs.
    Uses atomic writes to prevent file corruption during cloud/local execution.
    """

    def __init__(self, state_path: Optional[str | Path] = None):
        if state_path:
            self.state_path = Path(state_path)
        else:
            self.state_path = DEFAULT_STATE_PATH

        self._has_changes = False
        self._data: dict = {
            "version": 1,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "stats": {"total_jobs": 0, "total_notified": 0},
            "jobs": {},
            "source_runs": [],
            "recent_exclusions": [],
            "uae_sources": [],
        }
        self.load_state()

    # ------------------------------------------------------------------
    # State Persistence & Atomic Writes
    # ------------------------------------------------------------------

    def load_state(self) -> None:
        """Load state from state_path, or legacy fallback only for the default state file."""
        target = self.state_path
        if (
            not target.exists()
            and self.state_path == DEFAULT_STATE_PATH
            and LEGACY_FALLBACK_PATH.exists()
        ):
            target = LEGACY_FALLBACK_PATH
            logger.info("Loading initial state from fallback file: %s", target)

        if target.exists():
            try:
                raw = json.loads(target.read_text(encoding="utf-8"))
                # Handle old schema where root was just {"jobs": ..., "source_runs": ...}
                if "jobs" in raw and isinstance(raw["jobs"], dict):
                    self._data["jobs"] = raw["jobs"]
                if "source_runs" in raw and isinstance(raw["source_runs"], list):
                    self._data["source_runs"] = raw["source_runs"]
                if "recent_exclusions" in raw and isinstance(raw["recent_exclusions"], list):
                    self._data["recent_exclusions"] = raw["recent_exclusions"]
                if "uae_sources" in raw and isinstance(raw["uae_sources"], list):
                    self._data["uae_sources"] = raw["uae_sources"]
                if "version" in raw:
                    self._data["version"] = raw["version"]
                if "stats" in raw and isinstance(raw["stats"], dict):
                    self._data["stats"] = raw["stats"]
                if "last_updated" in raw:
                    self._data["last_updated"] = raw["last_updated"]

                logger.info(
                    "Loaded state from %s: %d known jobs, %d source run records",
                    target,
                    len(self._data["jobs"]),
                    len(self._data["source_runs"]),
                )
            except Exception as exc:
                logger.error("Failed to parse state file %s: %s (preserving empty state)", target, exc)

    def save_state(self) -> bool:
        """
        Atomically write state to disk.
        Writes to a temporary file first, then replaces target file to avoid corruption.
        """
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self._data["last_updated"] = datetime.now(timezone.utc).isoformat()
            self._data["stats"] = {
                "total_jobs": len(self._data["jobs"]),
                "total_notified": sum(1 for j in self._data["jobs"].values() if j.get("notified")),
            }

            content = json.dumps(self._data, indent=2, ensure_ascii=False)

            # Atomic write via temp file in same directory
            temp_file = self.state_path.with_suffix(".tmp")
            temp_file.write_text(content, encoding="utf-8")
            temp_file.replace(self.state_path)

            self._has_changes = False
            logger.info(
                "Successfully saved state to %s (%d jobs stored)",
                self.state_path,
                len(self._data["jobs"]),
            )
            return True
        except Exception as exc:
            logger.error("Failed to atomically save state to %s: %s", self.state_path, exc)
            return False

    @property
    def has_changes(self) -> bool:
        return self._has_changes

    # ------------------------------------------------------------------
    # Public Job Operations
    # ------------------------------------------------------------------

    def upsert_job(self, job_dict: dict) -> bool:
        """Insert or update a job listing by its fingerprint."""
        fp = job_dict.get("fingerprint")
        if not fp:
            logger.warning("Attempted to upsert job without fingerprint: %s", job_dict.get("title"))
            return False

        existing = self._data["jobs"].get(fp)
        if existing:
            # Preserve user application_status if previously modified
            user_status = existing.get("application_status", "new")
            if user_status in ("saved", "applied", "dismissed"):
                job_dict["application_status"] = user_status
            # Preserve notified flag if already notified
            if existing.get("notified"):
                job_dict["notified"] = True
            # Preserve original discovery timestamps across subsequent checks
            if existing.get("first_seen_at"):
                job_dict["first_seen_at"] = existing["first_seen_at"]
            if existing.get("detected_at"):
                job_dict["detected_at"] = existing["detected_at"]
        elif not job_dict.get("first_seen_at") and job_dict.get("detected_at"):
            job_dict["first_seen_at"] = job_dict["detected_at"]

        self._data["jobs"][fp] = job_dict
        self._has_changes = True
        return True

    def upsert_jobs(self, job_dicts: list[dict]) -> int:
        """Bulk upsert job dictionaries. Automatically saves to disk."""
        count = 0
        for job in job_dicts:
            if self.upsert_job(job):
                count += 1
        if count > 0:
            self.save_state()
        return count

    def get_known_fingerprints(self) -> list[str]:
        """Return all known job fingerprints for deduplication."""
        return list(self._data["jobs"].keys())

    def get_unnotified_jobs(self, min_score: int = 50) -> list[dict]:
        """Return list of matching jobs that have not yet generated a notification."""
        unnotified = []
        for job in self._data["jobs"].values():
            if not job.get("notified") and job.get("match_score", 0) >= min_score:
                unnotified.append(job)
        # Sort newest first
        unnotified.sort(key=lambda j: j.get("detected_at", ""), reverse=True)
        return unnotified

    def mark_notified(self, fingerprints: list[str]) -> None:
        """Mark the given job fingerprints as notified and persist."""
        now_str = datetime.now(timezone.utc).isoformat()
        marked = 0
        for fp in fingerprints:
            if fp in self._data["jobs"]:
                self._data["jobs"][fp]["notified"] = True
                self._data["jobs"][fp]["notified_at"] = now_str
                marked += 1
        if marked > 0:
            self._has_changes = True
            self.save_state()

    def get_jobs(
        self,
        min_score: int = 0,
        status: Optional[str] = None,
        limit: int = 200,
        max_age_hours: Optional[float] = None,
    ) -> list[dict]:
        """Fetch jobs matching criteria, optionally enforcing UTC posting age window."""
        from backend.core.time_utils import parse_utc_timestamp

        now_utc = datetime.now(timezone.utc)
        results = []
        for job in self._data["jobs"].values():
            if (job.get("match_score", 0) or 0) < min_score:
                continue
            job_status = job.get("application_status", "new")
            if status and job_status != status:
                continue
            if max_age_hours is not None and job_status not in ("saved", "applied"):
                if job.get("timestamp_reliable") is False:
                    continue
                posted_dt, _, reliable = parse_utc_timestamp(job.get("posted_at"))
                if posted_dt is None or not reliable:
                    continue
                age_hours = (now_utc - posted_dt).total_seconds() / 3600.0
                if age_hours < 0 or age_hours > max_age_hours:
                    continue
            results.append(job)

        results.sort(key=lambda j: j.get("posted_at") or j.get("detected_at", ""), reverse=True)
        return results[:limit]

    # ------------------------------------------------------------------
    # Source Health Logging
    # ------------------------------------------------------------------

    def log_source_run(
        self,
        source: str,
        success: bool,
        jobs_found: int,
        error: str = "",
    ) -> None:
        """Log the result of an adapter run for monitoring & dashboard stats."""
        record = {
            "source": source,
            "success": success,
            "jobs_found": jobs_found,
            "error": error[:500] if error else "",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        self._data["source_runs"].insert(0, record)
        # Keep last 500 run records to prevent unbounded file growth
        self._data["source_runs"] = self._data["source_runs"][:500]
        self._has_changes = True

    def log_excluded_job(self, job_dict: dict) -> None:
        """Record debugging metadata for jobs excluded by the posting age filter."""
        record = {
            "source": job_dict.get("source", ""),
            "source_id": job_dict.get("source_id", ""),
            "title": job_dict.get("title", ""),
            "company": job_dict.get("company", ""),
            "source_timestamp_raw": job_dict.get("source_timestamp_raw", ""),
            "posted_at": job_dict.get("posted_at"),
            "detected_at": job_dict.get("detected_at"),
            "exclusion_reason": job_dict.get("exclusion_reason", ""),
        }
        exclusions = self._data.setdefault("recent_exclusions", [])
        exclusions.insert(0, record)
        self._data["recent_exclusions"] = exclusions[:50]
        self._has_changes = True

    def set_uae_sources(self, uae_sources: list[dict]) -> None:
        """Persist UAE source catalog and latest check metadata for extension display."""
        self._data["uae_sources"] = uae_sources
        self._has_changes = True

    def get_uae_sources(self) -> list[dict]:
        """Return persisted UAE source status entries."""
        return list(self._data.get("uae_sources", []))

    def get_source_stats(self) -> list[dict]:
        """Aggregate per-source run health statistics."""
        from collections import defaultdict
        stats: dict[str, dict] = defaultdict(lambda: {
            "source": "",
            "total_runs": 0,
            "successful_runs": 0,
            "last_checked": None,
            "last_success": None,
            "last_error": "",
            "total_jobs": 0,
        })
        for row in self._data.get("source_runs", []):
            s = row.get("source", "unknown")
            stats[s]["source"] = s
            stats[s]["total_runs"] += 1
            stats[s]["total_jobs"] += row.get("jobs_found", 0)
            if row.get("success"):
                stats[s]["successful_runs"] += 1
                if not stats[s]["last_success"]:
                    stats[s]["last_success"] = row.get("checked_at")
            else:
                if not stats[s]["last_error"]:
                    stats[s]["last_error"] = row.get("error", "")
            if not stats[s]["last_checked"]:
                stats[s]["last_checked"] = row.get("checked_at")

        return list(stats.values())
