# job_module/formatter.py
# ============================================================
# Job Formatter
# Converts a structured job dict into a Telegram-ready string.
# ============================================================

from __future__ import annotations

import textwrap
from datetime import datetime, timezone

from job_module.logger import get_logger

logger = get_logger(__name__)

# Maximum length Telegram allows per message (4096 chars)
_TELEGRAM_MAX_CHARS = 4_000
_DESC_MAX_CHARS = 280


def _truncate(text: str, limit: int = _DESC_MAX_CHARS) -> str:
    """Truncate text to `limit` characters, appending '…' if cut."""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def format_job(job: dict[str, str], index: int = 1) -> str:
    """
    Format a single structured job dict into a Telegram message string.

    Args:
        job:   dict with keys role, company, location, skills, salary,
               description, apply_link
        index: 1-based job counter shown in the header

    Returns:
        A UTF-8 string ≤ 4000 characters suitable for Telegram sendMessage.
    """
    role        = job.get("role",        "Software Developer")
    company     = job.get("company",     "Unknown Company")
    location    = job.get("location",    "Remote")
    skills      = job.get("skills",      "Not specified")
    salary      = job.get("salary",      "Not disclosed")
    description = _truncate(job.get("description", "No description available."))
    apply_link  = job.get("apply_link",  "N/A")

    message = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔥 *Job #{index} — {role}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏢 *Company:*  {company}\n"
        f"📍 *Location:* {location}\n"
        f"🛠 *Skills:*   {skills}\n"
        f"💰 *Salary:*   {salary}\n\n"
        f"📌 *About the Role:*\n"
        f"{description}\n\n"
        f"🔗 *Apply Here:*\n"
        f"{apply_link}\n"
    )

    # Hard-cap to Telegram's limit
    if len(message) > _TELEGRAM_MAX_CHARS:
        message = message[:_TELEGRAM_MAX_CHARS - 3] + "…"

    return message


def format_header(query: str, total_jobs: int) -> str:
    """Intro banner sent before the individual job posts."""
    now = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    return (
        f"🚀 *AutoJob Broadcast*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔍 Query:  `{query}`\n"
        f"📊 Jobs found: *{total_jobs}*\n"
        f"🕐 Time: {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_footer() -> str:
    """Closing message after all jobs have been sent."""
    return (
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *That's all for now!*\n"
        "👆 Apply early — opportunities don't wait.\n"
        "📢 Stay tuned for the next broadcast.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def format_all_jobs(
    jobs: list[dict[str, str]],
    query: str = "Tech Jobs",
) -> list[str]:
    """
    Format all jobs into a list of Telegram-ready message strings.
    Order: [header, job_1, job_2, …, footer]

    Args:
        jobs:  list of structured job dicts
        query: search keyword shown in the header

    Returns:
        list of message strings ready for telegram_sender.
    """
    if not jobs:
        logger.warning("No jobs to format.")
        return []

    messages: list[str] = [format_header(query, len(jobs))]

    for idx, job in enumerate(jobs, start=1):
        try:
            messages.append(format_job(job, index=idx))
        except Exception as exc:
            logger.error("Failed to format job #%d: %s", idx, exc)

    messages.append(format_footer())

    logger.info("✅ Formatted %d messages (header + %d jobs + footer)", len(messages), len(jobs))
    return messages
