# job_module/main_job.py
# ============================================================
# 🚀 AutoJob Broadcast — Main Pipeline
# ============================================================
# Full pipeline:
#   scrape → deduplicate → AI-process → format → send to Telegram
#
# Entry points
# ─────────────
#   run_job_broadcast()  — run the full pipeline once
#   main()               — CLI entry point (also runs once)
# ============================================================

from __future__ import annotations

import sys
import traceback

from job_module.config import SCRAPE_LOCATION, SCRAPE_MAX_JOBS, SCRAPE_QUERY
from job_module.logger import get_logger

logger = get_logger(__name__)


# ════════════════════════════════════════════════════════════
# Core pipeline
# ════════════════════════════════════════════════════════════

def run_job_broadcast(
    query: str = SCRAPE_QUERY,
    location: str = SCRAPE_LOCATION,
    max_jobs: int = SCRAPE_MAX_JOBS,
) -> dict[str, int]:
    """
    Run the full job-broadcasting pipeline once.

    Steps
    -----
    1. Scrape jobs from RemoteOK, LinkedIn, WeWorkRemotely
    2. Deduplicate against previously sent jobs
    3. Structure each job via GPT-3.5 Turbo
    4. Format into Telegram messages
    5. Send to Telegram channel/chat

    Args:
        query:    Job search keyword (e.g. "Python developer")
        location: Preferred location (e.g. "Remote", "New York")
        max_jobs: Maximum number of jobs to scrape per run

    Returns:
        Summary dict:
        {
            "scraped":    N,   # raw jobs collected
            "new":        N,   # after cross-run dedup
            "processed":  N,   # successfully structured by AI
            "sent":       N,   # successfully sent to Telegram
            "failed":     N,   # failed Telegram sends
        }
    """
    summary = {
        "scraped": 0,
        "new": 0,
        "processed": 0,
        "sent": 0,
        "failed": 0,
    }

    logger.info("=" * 60)
    logger.info("🚀 AutoJob Broadcast — pipeline starting")
    logger.info("   Query: %s | Location: %s | Max: %d", query, location, max_jobs)
    logger.info("=" * 60)

    # ── Step 1: Scrape ───────────────────────────────────────
    try:
        from job_module.scraper import scrape_jobs
        raw_jobs = scrape_jobs(query=query, location=location, max_jobs=max_jobs)
        summary["scraped"] = len(raw_jobs)
        logger.info("Step 1 ✅  Scraped %d jobs", len(raw_jobs))
    except Exception:
        logger.error("Step 1 ❌  Scraper crashed:\n%s", traceback.format_exc())
        return summary

    if not raw_jobs:
        logger.warning("No jobs scraped — aborting pipeline.")
        return summary

    # ── Step 2: Deduplicate (cross-run) ─────────────────────
    try:
        from job_module.deduplicator import filter_new_jobs
        new_jobs = filter_new_jobs(raw_jobs)
        summary["new"] = len(new_jobs)
        logger.info("Step 2 ✅  %d new jobs (after dedup)", len(new_jobs))
    except Exception:
        logger.error("Step 2 ❌  Deduplicator crashed:\n%s", traceback.format_exc())
        new_jobs = raw_jobs   # Proceed without dedup on error

    if not new_jobs:
        logger.info("All scraped jobs were already sent. Nothing new to broadcast.")
        return summary

    # ── Step 3: AI structuring ───────────────────────────────
    try:
        from job_module.ai_processor import process_jobs
        structured_jobs = process_jobs(new_jobs)
        summary["processed"] = len(structured_jobs)
        logger.info("Step 3 ✅  Structured %d jobs via GPT-3.5", len(structured_jobs))
    except Exception:
        logger.error("Step 3 ❌  AI processor crashed:\n%s", traceback.format_exc())
        return summary

    if not structured_jobs:
        logger.warning("No jobs survived AI processing — aborting.")
        return summary

    # ── Step 4: Format ───────────────────────────────────────
    try:
        from job_module.formatter import format_all_jobs
        messages = format_all_jobs(structured_jobs, query=query)
        logger.info("Step 4 ✅  Formatted %d messages", len(messages))
    except Exception:
        logger.error("Step 4 ❌  Formatter crashed:\n%s", traceback.format_exc())
        return summary

    # ── Step 5: Send to Telegram ─────────────────────────────
    try:
        from job_module.telegram_sender import send_jobs_to_telegram
        result = send_jobs_to_telegram(messages)
        summary["sent"] = result["sent"]
        summary["failed"] = result["failed"]
        logger.info(
            "Step 5 ✅  Telegram — sent: %d | failed: %d",
            result["sent"],
            result["failed"],
        )
    except Exception:
        logger.error("Step 5 ❌  Telegram sender crashed:\n%s", traceback.format_exc())

    # ── Summary ──────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("📊 Run summary: %s", summary)
    logger.info("=" * 60)

    return summary


# ════════════════════════════════════════════════════════════
# CLI entry point
# ════════════════════════════════════════════════════════════

def main() -> None:
    """
    CLI entry point — runs the pipeline once and exits.
    Usage:
        python -m job_module.main_job
    or via scheduler.py for scheduled runs.
    """
    try:
        result = run_job_broadcast()
        if result["sent"] == 0 and result["scraped"] == 0:
            logger.warning("Pipeline produced no output — check logs above.")
            sys.exit(1)
        sys.exit(0)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)
    except Exception:
        logger.critical("Unhandled exception in main:\n%s", traceback.format_exc())
        sys.exit(2)


if __name__ == "__main__":
    main()
