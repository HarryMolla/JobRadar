"""
Lightweight HTTP API server for the Chrome extension.
Runs locally (or on a free host) to serve job data to the extension.
Uses only Python standard library + supabase-py — no web framework needed.

Endpoints:
  GET  /jobs         - List jobs with optional filters
  GET  /jobs/stats   - Source health statistics
  POST /jobs/update  - Update application_status of a job
  GET  /health       - Health check

Security:
  - Binds to localhost by default (not exposed to internet).
  - For cloud hosting on Render/Railway free tier, set HOST=0.0.0.0
    and protect with a simple API key (set via API_KEY env var).
"""
from __future__ import annotations

import json
import logging
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

API_KEY = os.environ.get("API_KEY", "")  # Empty = no auth (localhost only)
HOST = os.environ.get("API_HOST", "127.0.0.1")
PORT = int(os.environ.get("API_PORT", "8765"))


def _cors_headers() -> dict:
    return {
        "Access-Control-Allow-Origin": "chrome-extension://",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, X-API-Key",
    }


class JobRadarHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info("API %s %s", self.address_string(), format % args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, msg, status=400):
        self._send_json({"error": msg}, status)

    def _check_auth(self) -> bool:
        if not API_KEY:
            return True  # localhost mode — no auth
        provided = self.headers.get("X-API-Key", "")
        return provided == API_KEY

    def do_OPTIONS(self):
        self.send_response(204)
        for k, v in _cors_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def do_GET(self):
        if not self._check_auth():
            self._send_error("Unauthorized", 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        def qp(key, default=None):
            vals = params.get(key, [])
            return vals[0] if vals else default

        try:
            from backend.core.config import get_config
            from backend.core.storage import Storage
            cfg = get_config()
            storage = Storage(cfg.state_file_path)

            if path == "/jobs":
                min_score = int(qp("min_score", "0"))
                status = qp("status")
                limit = int(qp("limit", "200"))
                max_age_param = qp("max_age_hours")
                max_age_hours = (
                    float(max_age_param)
                    if max_age_param is not None
                    else cfg.max_posting_age_hours
                )
                if status in ("saved", "applied"):
                    max_age_hours = None
                jobs = storage.get_jobs(
                    min_score=min_score,
                    status=status,
                    limit=limit,
                    max_age_hours=max_age_hours,
                )
                self._send_json({"jobs": jobs, "count": len(jobs)})

            elif path == "/jobs/stats":
                stats = storage.get_source_stats()
                self._send_json({"sources": stats})

            elif path == "/sources/uae":
                from backend.adapters.uae_sources import build_uae_source_status
                uae_sources = build_uae_source_status(storage._data.get("source_runs", []))
                self._send_json({"uae_sources": uae_sources})

            elif path == "/health":
                self._send_json({"status": "ok", "version": "1.0.0"})

            else:
                self._send_error("Not found", 404)

        except Exception as exc:
            logger.error("API error: %s", exc, exc_info=True)
            self._send_error(str(exc), 500)

    def do_POST(self):
        if not self._check_auth():
            self._send_error("Unauthorized", 401)
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(length)) if length else {}

            from backend.core.config import get_config
            from backend.core.storage import Storage
            cfg = get_config()
            storage = Storage(cfg.state_file_path)

            if path == "/jobs/update":
                fp = body.get("fingerprint")
                new_status = body.get("application_status")
                if not fp or not new_status:
                    self._send_error("fingerprint and application_status required")
                    return
                allowed = {"new", "saved", "applied", "dismissed"}
                if new_status not in allowed:
                    self._send_error(f"application_status must be one of {allowed}")
                    return
                # Update in repository storage
                if fp in storage._data["jobs"]:
                    storage._data["jobs"][fp]["application_status"] = new_status
                    storage.save_state()
                self._send_json({"ok": True, "fingerprint": fp, "status": new_status})

            else:
                self._send_error("Not found", 404)

        except Exception as exc:
            logger.error("API POST error: %s", exc, exc_info=True)
            self._send_error(str(exc), 500)


def start_server():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    server = HTTPServer((HOST, PORT), JobRadarHandler)
    logger.info("JobRadar API server running at http://%s:%d", HOST, PORT)
    logger.info("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server stopped")


if __name__ == "__main__":
    start_server()
