"""
Main collector entry point.
Orchestrates all adapters → matcher → deduplicator → storage → notifier.
"""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Configure logging before any imports
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("collector")


def run_collection() -> None:
    """Main collection loop. Run all adapters, match, deduplicate, store, notify."""
    from backend.core.config import get_config
    from backend.core.matcher import JobMatcher
    from backend.core.storage import Storage
    from backend.core.deduplicator import Deduplicator
    from backend.core.notifier import GmailNotifier, TelegramNotifier
    from backend.adapters.registry import get_enabled_adapters, load_sources_config

    config = get_config()

    # Validate config
    warnings = config.validate()
    for warn in warnings:
        logger.warning("Config notice: %s", warn)

    # Initialize components with repository-based state storage
    storage = Storage(state_path=config.state_file_path)
    deduplicator = Deduplicator(storage)
    matcher = JobMatcher()

    sources_config = load_sources_config()
    disabled = sources_config.get("disabled_sources", [])
    adapters = get_enabled_adapters(disabled_sources=disabled, sources_config=sources_config)

    logger.info("Starting collection run with %d adapters", len(adapters))
    start_time = datetime.now(timezone.utc)

    all_new_jobs = []
    source_results = []

    for adapter in adapters:
        logger.info("--- Running adapter: %s ---", adapter.DISPLAY_NAME)
        result = adapter.run()
        source_results.append(result)

        # Log run to storage
        storage.log_source_run(
            source=result.source,
            success=result.success,
            jobs_found=len(result.jobs),
            error=result.error,
        )

        if not result.success or not result.jobs:
            if result.error:
                logger.warning("%s: %s", result.source, result.error)
            continue

        # Match jobs
        matched = []
        for job in result.jobs:
            matcher.match(job)
            if job.match_score >= config.min_match_score:
                matched.append(job)

        logger.info(
            "%s: %d total → %d matched (score >= %d)",
            result.source, len(result.jobs), len(matched), config.min_match_score
        )

        # Deduplicate
        new_jobs = deduplicator.filter_new(matched)
        logger.info("%s: %d are genuinely new", result.source, len(new_jobs))

        # Store
        if new_jobs:
            count = storage.upsert_jobs([j.to_dict() for j in new_jobs])
            for job in new_jobs:
                deduplicator.mark_seen(job)
            all_new_jobs.extend(new_jobs)
            logger.info("%s: stored %d new jobs", result.source, count)

    logger.info(
        "Collection complete: %d total new matching jobs across all sources",
        len(all_new_jobs)
    )

    # Send notifications for jobs above notification threshold
    notify_jobs = [
        j for j in all_new_jobs
        if j.match_score >= config.notification_min_score
    ]

    if notify_jobs:
        notify_dicts = [j.to_dict() for j in notify_jobs]
        notified = False

        if config.has_gmail:
            try:
                notifier = GmailNotifier(
                    credentials_json=config.gmail_credentials_json,
                    token_json=config.gmail_token_json,
                    sender_email=config.notification_email,
                )
                ok = notifier.send_digest(notify_dicts, to_email=config.notification_email)
                if ok:
                    fps = [j.fingerprint for j in notify_jobs]
                    storage.mark_notified(fps)
                    notified = True
                    logger.info("Gmail digest sent: %d jobs", len(notify_jobs))
            except Exception as exc:
                logger.error("Gmail notification failed: %s", exc)

        if not notified and config.has_telegram:
            try:
                tg = TelegramNotifier(config.telegram_bot_token, config.telegram_chat_id)
                ok = tg.send_digest(notify_dicts)
                if ok:
                    fps = [j.fingerprint for j in notify_jobs]
                    storage.mark_notified(fps)
                    logger.info("Telegram digest sent: %d jobs", len(notify_jobs))
            except Exception as exc:
                logger.error("Telegram notification failed: %s", exc)

        if not notified:
            logger.warning(
                "No notification method configured. "
                "Set up Gmail (GMAIL_CREDENTIALS_JSON/GMAIL_TOKEN_JSON) or "
                "Telegram (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID) to receive alerts."
            )
    else:
        logger.info("No new jobs above notification threshold (%d)", config.notification_min_score)

    # Persist all updates to repository storage
    storage.save_state()

    # Summary
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    success_count = sum(1 for r in source_results if r.success)
    fail_count = len(source_results) - success_count
    logger.info(
        "Run summary: %.1fs elapsed | %d sources OK | %d failed | %d new jobs stored | %d notifications sent",
        duration, success_count, fail_count, len(all_new_jobs), len(notify_jobs) if notify_jobs else 0
    )


if __name__ == "__main__":
    run_collection()
