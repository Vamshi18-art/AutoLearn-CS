# job_module/scheduler.py
# ============================================================
# AutoJob Scheduler
# Uses APScheduler (blocking scheduler — no infinite loops).
# Runs the full broadcast pipeline on a configurable schedule
# and exits cleanly after the scheduler is stopped.
# ============================================================

from __future__ import annotations

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from job_module.config import (
    SCHEDULE_DAILY_TIME,
    SCHEDULE_INTERVAL_HOURS,
    SCHEDULE_MODE,
    SCRAPE_LOCATION,
    SCRAPE_MAX_JOBS,
    SCRAPE_QUERY,
)
from job_module.logger import get_logger
from job_module.main_job import run_job_broadcast

logger = get_logger(__name__)

# ── APScheduler instance (module-level so signal handler can stop it) ────────
_scheduler = BlockingScheduler(timezone="UTC")


# ════════════════════════════════════════════════════════════
# Scheduled job wrapper
# ════════════════════════════════════════════════════════════

def _scheduled_broadcast() -> None:
    """Wrapper called by APScheduler on each trigger."""
    logger.info("⏰ Scheduled trigger fired — starting broadcast …")
    try:
        run_job_broadcast(
            query=SCRAPE_QUERY,
            location=SCRAPE_LOCATION,
            max_jobs=SCRAPE_MAX_JOBS,
        )
    except Exception as exc:
        # Never let a failed run crash the scheduler
        logger.error("Scheduled broadcast raised an exception: %s", exc, exc_info=True)


# ════════════════════════════════════════════════════════════
# Signal handling — graceful shutdown on Ctrl-C or SIGTERM
# ════════════════════════════════════════════════════════════

def _shutdown(signum, frame):
    logger.info("📴 Shutdown signal received — stopping scheduler …")
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)


# ════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════

def start_scheduler(run_immediately: bool = True) -> None:
    """
    Configure and start the APScheduler blocking scheduler.

    Args:
        run_immediately: If True, run the broadcast once right now before
                         the first scheduled interval/cron fires.

    Blocks until the process receives SIGINT / SIGTERM.
    Does NOT use infinite loops.
    """
    # ── Choose trigger based on config ───────────────────────
    if SCHEDULE_MODE == "daily":
        hour_str, minute_str = SCHEDULE_DAILY_TIME.split(":")
        trigger = CronTrigger(hour=int(hour_str), minute=int(minute_str), timezone="UTC")
        schedule_desc = f"daily at {SCHEDULE_DAILY_TIME} UTC"
    else:  # "interval"
        trigger = IntervalTrigger(hours=SCHEDULE_INTERVAL_HOURS)
        schedule_desc = f"every {SCHEDULE_INTERVAL_HOURS} hour(s)"

    _scheduler.add_job(
        _scheduled_broadcast,
        trigger=trigger,
        id="job_broadcast",
        name="AutoJob Broadcast",
        replace_existing=True,
        max_instances=1,            # Prevent overlapping runs
        misfire_grace_time=300,     # 5-minute grace window
    )

    logger.info("⏰ Scheduler configured — mode: %s (%s)", SCHEDULE_MODE, schedule_desc)

    # Optionally run the pipeline immediately on startup
    if run_immediately:
        logger.info("▶️  Running broadcast immediately (run_immediately=True) …")
        _scheduled_broadcast()

    logger.info("🔄 Scheduler started — waiting for next trigger …")
    logger.info("   Press Ctrl-C or send SIGTERM to stop.")

    try:
        _scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")


# ════════════════════════════════════════════════════════════
# CLI usage:  python -m job_module.scheduler
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    start_scheduler(run_immediately=True)
