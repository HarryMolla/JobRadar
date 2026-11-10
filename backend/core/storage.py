"""
Persistent storage via Supabase (PostgREST REST API).
Falls back to a local JSON file when Supabase is not configured (dev mode).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class Storage:
    """
    Thin wrapper around Supabase REST API.
    Uses supabase-py client when available.
    """

    def __init__(self, supabase_url: str, supabase_key: str):
        self.url = supabase_url
        self.key = supabase_key
        self._client = None
        self._fallback_path = Path("jobs_fallback.json")

        if supabase_url and supabase_key:
            try:
                from supabase import create_client, Client
                self._client = create_client(supabase_url, supabase_key)
                logger.info("Supabase client initialized: %s", supabase_url)
            except Exception as exc:
                logger.error("Failed to init Supabase client: %s", exc)
        else:
            logger.warning(
                "Supabase not configured — using local JSON fallback (%s).",
                self._fallback_path,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def upsert_job(self, job_dict: dict) -> bool:
        """Insert or update a job. Returns True on success."""
        if self._client:
            return self._upsert_supabase(job_dict)
        return self._upsert_local(job_dict)

    def upsert_jobs(self, job_dicts: list[dict]) -> int:
        """Bulk upsert. Returns count of successful upserts."""
        count = 0
        for job in job_dicts:
            if self.upsert_job(job):
                count += 1
        return count

    def get_known_fingerprints(self) -> list[str]:
        """Return all fingerprints stored to date (for deduplication)."""
        if self._client:
            return self._get_fingerprints_supabase()
        return self._get_fingerprints_local()

    def get_unnotified_jobs(self, min_score: int = 50) -> list[dict]:
        """Return jobs that have not yet triggered a notification."""
        if self._client:
            return self._get_unnotified_supabase(min_score)
        return self._get_unnotified_local(min_score)

    def mark_notified(self, fingerprints: list[str]) -> None:
        """Mark jobs as notified by their fingerprint."""
        if self._client:
            self._mark_notified_supabase(fingerprints)
        else:
            self._mark_notified_local(fingerprints)

    def get_jobs(
        self,
        min_score: int = 0,
        status: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        """Fetch jobs with optional filters."""
        if self._client:
            return self._get_jobs_supabase(min_score, status, limit)
        return self._get_jobs_local(min_score, status, limit)

    def get_source_stats(self) -> list[dict]:
        """Return per-source statistics."""
        if self._client:
            return self._get_source_stats_supabase()
        return []

    def log_source_run(self, source: str, success: bool, jobs_found: int, error: str = "") -> None:
        """Record a collector run result for a source."""
        record = {
            "source": source,
            "success": success,
            "jobs_found": jobs_found,
            "error": error[:500] if error else "",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        if self._client:
            try:
                self._client.table("source_runs").insert(record).execute()
            except Exception as exc:
                logger.error("Failed to log source run for %s: %s", source, exc)

    # ------------------------------------------------------------------
    # Supabase implementations
    # ------------------------------------------------------------------

    def _upsert_supabase(self, job: dict) -> bool:
        try:
            self._client.table("jobs").upsert(
                job, on_conflict="fingerprint"
            ).execute()
            return True
        except Exception as exc:
            logger.error("Supabase upsert failed: %s", exc)
            return False

    def _get_fingerprints_supabase(self) -> list[str]:
        try:
            resp = (
                self._client.table("jobs")
                .select("fingerprint")
                .execute()
            )
            return [row["fingerprint"] for row in resp.data]
        except Exception as exc:
            logger.error("Failed to fetch fingerprints: %s", exc)
            return []

    def _get_unnotified_supabase(self, min_score: int) -> list[dict]:
        try:
            resp = (
                self._client.table("jobs")
                .select("*")
                .eq("notified", False)
                .gte("match_score", min_score)
                .order("detected_at", desc=True)
                .limit(50)
                .execute()
            )
            return resp.data
        except Exception as exc:
            logger.error("Failed to fetch unnotified jobs: %s", exc)
            return []

    def _mark_notified_supabase(self, fingerprints: list[str]) -> None:
        try:
            self._client.table("jobs").update({"notified": True}).in_(
                "fingerprint", fingerprints
            ).execute()
        except Exception as exc:
            logger.error("Failed to mark notified: %s", exc)

    def _get_jobs_supabase(
        self, min_score: int, status: Optional[str], limit: int
    ) -> list[dict]:
        try:
            q = (
                self._client.table("jobs")
                .select("*")
                .gte("match_score", min_score)
                .order("detected_at", desc=True)
                .limit(limit)
            )
            if status:
                q = q.eq("application_status", status)
            return q.execute().data
        except Exception as exc:
            logger.error("Failed to fetch jobs: %s", exc)
            return []

    def _get_source_stats_supabase(self) -> list[dict]:
        try:
            resp = (
                self._client.table("source_runs")
                .select("source, success, jobs_found, checked_at, error")
                .order("checked_at", desc=True)
                .limit(500)
                .execute()
            )
            # Aggregate by source
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
            for row in resp.data:
                s = row["source"]
                stats[s]["source"] = s
                stats[s]["total_runs"] += 1
                stats[s]["total_jobs"] += row.get("jobs_found", 0)
                if row["success"]:
                    stats[s]["successful_runs"] += 1
                    if not stats[s]["last_success"]:
                        stats[s]["last_success"] = row["checked_at"]
                else:
                    if not stats[s]["last_error"]:
                        stats[s]["last_error"] = row.get("error", "")
                if not stats[s]["last_checked"]:
                    stats[s]["last_checked"] = row["checked_at"]
            return list(stats.values())
        except Exception as exc:
            logger.error("Failed to fetch source stats: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Local JSON fallback
    # ------------------------------------------------------------------

    def _load_local(self) -> dict:
        if self._fallback_path.exists():
            try:
                return json.loads(self._fallback_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"jobs": {}, "source_runs": []}

    def _save_local(self, data: dict) -> None:
        self._fallback_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _upsert_local(self, job: dict) -> bool:
        data = self._load_local()
        fp = job.get("fingerprint", "")
        if fp:
            data["jobs"][fp] = job
            self._save_local(data)
        return bool(fp)

    def _get_fingerprints_local(self) -> list[str]:
        data = self._load_local()
        return list(data.get("jobs", {}).keys())

    def _get_unnotified_local(self, min_score: int) -> list[dict]:
        data = self._load_local()
        return [
            j for j in data.get("jobs", {}).values()
            if not j.get("notified") and j.get("match_score", 0) >= min_score
        ]

    def _mark_notified_local(self, fingerprints: list[str]) -> None:
        data = self._load_local()
        for fp in fingerprints:
            if fp in data["jobs"]:
                data["jobs"][fp]["notified"] = True
        self._save_local(data)

    def _get_jobs_local(
        self, min_score: int, status: Optional[str], limit: int
    ) -> list[dict]:
        data = self._load_local()
        jobs = list(data.get("jobs", {}).values())
        jobs = [j for j in jobs if j.get("match_score", 0) >= min_score]
        if status:
            jobs = [j for j in jobs if j.get("application_status") == status]
        jobs.sort(key=lambda j: j.get("detected_at", ""), reverse=True)
        return jobs[:limit]
