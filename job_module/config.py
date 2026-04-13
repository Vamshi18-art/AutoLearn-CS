# job_module/config.py
# ============================================================
# CONFIGURATION — Fill in your credentials before running
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()

# ── OpenAI ───────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "sk-YOUR_OPENAI_KEY_HERE")
OPENAI_MODEL: str = "gpt-3.5-turbo"
OPENAI_MAX_TOKENS: int = 600
OPENAI_TEMPERATURE: float = 0.3

# ── Telegram ─────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "@your_channel_or_chat_id")
TELEGRAM_DELAY_SECONDS: float = 2.5      # Pause between messages to avoid flood limits
TELEGRAM_MAX_RETRIES: int = 3

# ── Scraper ──────────────────────────────────────────────────
SCRAPE_QUERY: str = "Python developer"   # Job search keyword
SCRAPE_LOCATION: str = "Remote"          # Location filter
SCRAPE_MAX_JOBS: int = 3              # Max jobs per run
SCRAPER_TIMEOUT_MS: int = 30_000        # Playwright navigation timeout (ms)
SCRAPER_HEADLESS: bool = True           # Run browser headlessly

# ── Scheduler ────────────────────────────────────────────────
# Options: "interval" or "daily"
SCHEDULE_MODE: str = "interval"
SCHEDULE_INTERVAL_HOURS: int = 6        # Used when mode = "interval"
SCHEDULE_DAILY_TIME: str = "09:00"      # Used when mode = "daily"  (HH:MM, 24 h)

# ── Deduplication ────────────────────────────────────────────
SEEN_JOBS_FILE: str = os.path.join(os.path.dirname(__file__), "seen_jobs.json")

# ── Logging ──────────────────────────────────────────────────
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"