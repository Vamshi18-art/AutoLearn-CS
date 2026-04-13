# job_module/deduplicator.py
# ============================================================
# Cross-run Deduplication
# Persists a set of seen job fingerprints to disk (JSON).
# Prevents re-sending the same job in future scheduler runs.
# ============================================================

from __future__ import annotations

import hashlib
import json
import os

from job_module.config import SEEN_JOBS_FILE
from job_module.logger import get_logger

logger = get_logger(__name__)


def _fingerprint(job: dict[str, str]) -> str:
    """Generate a stable SHA-1 fingerprint from (title, company, apply_link)."""
    raw = "|".join(
        [
            job.get("role", job.get("title", "")).lower().strip(),
            job.get("company", "").lower().strip(),
            job.get("apply_link", "").strip(),
        ]
    )
    return hashlib.sha1(raw.encode()).hexdigest()


def _load_seen() -> set[str]:
    if not os.path.exists(SEEN_JOBS_FILE):
        return set()
    try:
        with open(SEEN_JOBS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return set(data) if isinstance(data, list) else set()
    except Exception as exc:
        logger.warning("Could not load seen_jobs.json: %s", exc)
        return set()


def _save_seen(seen: set[str]) -> None:
    try:
        with open(SEEN_JOBS_FILE, "w", encoding="utf-8") as fh:
            json.dump(sorted(seen), fh, indent=2)
    except Exception as exc:
        logger.warning("Could not save seen_jobs.json: %s", exc)


def filter_new_jobs(jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Remove jobs that were already sent in a previous run.
    Saves new fingerprints back to disk.

    Args:
        jobs: list of structured job dicts

    Returns:
        Subset containing only jobs not seen before.
    """
    seen = _load_seen()
    new_jobs: list[dict[str, str]] = []
    new_fps: set[str] = set()

    for job in jobs:
        fp = _fingerprint(job)
        if fp not in seen:
            new_jobs.append(job)
            new_fps.add(fp)

    if new_fps:
        seen |= new_fps
        _save_seen(seen)

    logger.info(
        "Deduplication: %d new | %d already seen | %d total",
        len(new_jobs),
        len(jobs) - len(new_jobs),
        len(jobs),
    )
    return new_jobs
