# job_module/telegram_sender.py
# ============================================================
# Telegram Bot Sender
# Uses the Telegram Bot HTTP API (no third-party library needed)
# Supports: single message, batch send, retry on failure
# ============================================================

from __future__ import annotations

import time
from typing import Any

import requests

from job_module.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_DELAY_SECONDS,
    TELEGRAM_MAX_RETRIES,
)
from job_module.logger import get_logger

logger = get_logger(__name__)

# ── Telegram API base URL ────────────────────────────────────
_BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Telegram parse modes
PARSE_MODE_MARKDOWN = "Markdown"
PARSE_MODE_HTML = "HTML"


# ════════════════════════════════════════════════════════════
# Low-level send
# ════════════════════════════════════════════════════════════

def _send_request(
    endpoint: str,
    payload: dict[str, Any],
    timeout: int = 20,
) -> dict[str, Any]:
    """
    POST to a Telegram Bot API endpoint.
    Returns the JSON response dict.
    Raises requests.HTTPError on non-2xx responses.
    """
    url = f"{_BASE_URL}/{endpoint}"
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _send_message_raw(
    chat_id: str,
    text: str,
    parse_mode: str = PARSE_MODE_MARKDOWN,
    disable_web_page_preview: bool = True,
) -> dict[str, Any]:
    """Core send-message call (no retry)."""
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview,
    }
    return _send_request("sendMessage", payload)


# ════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════

def send_message(
    text: str,
    chat_id: str = TELEGRAM_CHAT_ID,
    parse_mode: str = PARSE_MODE_MARKDOWN,
    retries: int = TELEGRAM_MAX_RETRIES,
) -> bool:
    """
    Send a single text message to a Telegram chat with exponential-backoff retry.

    Args:
        text:       Message content (Markdown or HTML).
        chat_id:    Target channel/group/user. Defaults to config value.
        parse_mode: "Markdown" or "HTML".
        retries:    Number of retry attempts on failure.

    Returns:
        True on success, False if all retries exhausted.
    """
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("YOUR_"):
        logger.error("❌ TELEGRAM_BOT_TOKEN is not configured. Set it in .env or config.py")
        return False

    if not chat_id or chat_id.startswith("@your_"):
        logger.error("❌ TELEGRAM_CHAT_ID is not configured. Set it in .env or config.py")
        return False

    for attempt in range(1, retries + 1):
        try:
            result = _send_message_raw(chat_id, text, parse_mode)

            if result.get("ok"):
                logger.debug("✅ Message sent (attempt %d)", attempt)
                return True
            else:
                logger.warning(
                    "Telegram returned ok=False on attempt %d: %s",
                    attempt, result.get("description"),
                )

        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning("HTTP %s on attempt %d: %s", status, attempt, exc)

            # 429 Too Many Requests — respect retry_after
            if exc.response is not None and exc.response.status_code == 429:
                retry_after = exc.response.json().get("parameters", {}).get("retry_after", 5)
                logger.info("Rate-limited — waiting %s s", retry_after)
                time.sleep(retry_after)
                continue

        except requests.exceptions.RequestException as exc:
            logger.warning("Network error on attempt %d: %s", attempt, exc)

        # Exponential back-off before next retry
        if attempt < retries:
            wait = 2 ** attempt
            logger.debug("Retrying in %d s …", wait)
            time.sleep(wait)

    logger.error("❌ Failed to send message after %d attempts", retries)
    return False


def send_jobs_to_telegram(
    messages: list[str],
    chat_id: str = TELEGRAM_CHAT_ID,
    delay: float = TELEGRAM_DELAY_SECONDS,
) -> dict[str, int]:
    """
    Send a list of pre-formatted job messages to Telegram sequentially.

    Args:
        messages: List of message strings (from formatter.format_all_jobs).
        chat_id:  Target channel/group/user.
        delay:    Pause (seconds) between messages to respect rate limits.

    Returns:
        A summary dict: {"sent": N, "failed": M, "total": T}
    """
    if not messages:
        logger.warning("No messages to send.")
        return {"sent": 0, "failed": 0, "total": 0}

    sent = 0
    failed = 0
    total = len(messages)

    logger.info("📨 Sending %d messages to Telegram …", total)

    for idx, msg in enumerate(messages, start=1):
        success = send_message(msg, chat_id=chat_id)
        if success:
            sent += 1
            logger.info("  [%d/%d] ✅ Sent", idx, total)
        else:
            failed += 1
            logger.error("  [%d/%d] ❌ Failed", idx, total)

        # Respect Telegram flood-control between messages
        if idx < total:
            time.sleep(delay)

    logger.info("📊 Telegram summary — sent: %d | failed: %d | total: %d", sent, failed, total)
    return {"sent": sent, "failed": failed, "total": total}


def test_connection(chat_id: str = TELEGRAM_CHAT_ID) -> bool:
    """
    Send a lightweight test message to verify bot token & chat ID are correct.
    Returns True on success.
    """
    logger.info("🔧 Testing Telegram connection …")
    test_text = (
        "🤖 *AutoJob Bot* — connection test\n"
        "If you see this, your bot is configured correctly! ✅"
    )
    return send_message(test_text, chat_id=chat_id, retries=1)
