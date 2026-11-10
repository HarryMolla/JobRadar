"""
Local runner for the collector. Use during development.
Usage: python scripts/run_collector.py [--dry-run] [--source SOURCE_ID]
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

def main():
    parser = argparse.ArgumentParser(description="JobRadar Collector")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and match jobs but don't store or notify")
    parser.add_argument("--source", type=str, default=None,
                        help="Run only this adapter (by SOURCE_ID)")
    parser.add_argument("--min-score", type=int, default=None,
                        help="Override minimum match score")
    args = parser.parse_args()

    if args.dry_run:
        print("DRY RUN MODE — no storage or notifications")

    if args.source:
        print(f"Running only adapter: {args.source}")

    if args.min_score is not None:
        import os
        os.environ["MIN_MATCH_SCORE"] = str(args.min_score)

    from backend.core.config import get_config
    from backend.core.matcher import JobMatcher
    from backend.adapters.registry import get_enabled_adapters, load_sources_config

    config = get_config()
    matcher = JobMatcher()
    sources_config = load_sources_config()
    disabled = sources_config.get("disabled_sources", [])

    if args.source:
        disabled = [
            a.SOURCE_ID for a in __import__(
                "backend.adapters.registry", fromlist=["ALL_ADAPTERS"]
            ).ALL_ADAPTERS
            if a.SOURCE_ID != args.source
        ]

    adapters = get_enabled_adapters(disabled_sources=disabled, sources_config=sources_config)

    for adapter in adapters:
        print(f"\n{'='*50}")
        print(f"Adapter: {adapter.DISPLAY_NAME}")
        result = adapter.run()
        if not result.success:
            print(f"  FAILED: {result.error}")
            continue
        print(f"  Fetched: {len(result.jobs)} jobs")
        matched = 0
        for job in result.jobs:
            matcher.match(job)
            if job.match_score >= config.min_match_score:
                matched += 1
                if args.dry_run:
                    print(f"  [{job.match_score:3d}] {job.title} @ {job.company} ({job.remote_type.value})")
                    if job.match_reasons:
                        print(f"        → {'; '.join(job.match_reasons[:3])}")
        print(f"  Matched: {matched}/{len(result.jobs)}")

    if not args.dry_run:
        from backend.collector import run_collection
        print("\nRunning full collection (with storage + notifications)...")
        run_collection()


if __name__ == "__main__":
    main()
