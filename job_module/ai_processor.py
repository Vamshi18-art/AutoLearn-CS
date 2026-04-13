# job_module/ai_processor.py
# ============================================================
# AI Job Structuring via GPT-3.5 Turbo
# Input : raw scraped job dict
# Output: clean structured job dict ready for formatting
# ============================================================

from __future__ import annotations

import json
import re
from typing import Any

import openai

from job_module.config import (
    OPENAI_API_KEY,
    OPENAI_MAX_TOKENS,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
)
from job_module.logger import get_logger

logger = get_logger(__name__)

# Initialise OpenAI client (SDK v1.x)
_client = openai.OpenAI(api_key=OPENAI_API_KEY)

# ── Prompt template ──────────────────────────────────────────
_SYSTEM_PROMPT = """
You are a professional job data structuring assistant.
Given raw job data, extract and return ONLY a valid JSON object with these exact keys:
  "role"        – job title (string)
  "company"     – company name (string)
  "location"    – job location (string, use "Remote" if not specified)
  "skills"      – comma-separated required skills (string, use "Not specified" if unknown)
  "salary"      – salary range (string, use "Not disclosed" if unknown)
  "description" – concise 2-3 sentence summary of the role (string)
  "apply_link"  – direct application URL (string)

Rules:
- Return ONLY the JSON object — no markdown, no explanation, no extra text.
- If a field is missing or unclear in the input, use a sensible default string.
- Keep the description under 300 characters.
- Do NOT invent information not present in the raw data.
""".strip()


def _build_user_prompt(raw_job: dict[str, str]) -> str:
    return (
        "Structure the following raw job data:\n\n"
        f"Title: {raw_job.get('title', 'N/A')}\n"
        f"Company: {raw_job.get('company', 'N/A')}\n"
        f"Location: {raw_job.get('location', 'N/A')}\n"
        f"Skills: {raw_job.get('skills', 'N/A')}\n"
        f"Salary: {raw_job.get('salary', 'N/A')}\n"
        f"Description: {raw_job.get('description', 'N/A')}\n"
        f"Apply Link: {raw_job.get('apply_link', 'N/A')}\n"
    )


def _extract_json(text: str) -> dict[str, Any]:
    """
    Robustly extract a JSON object from GPT output even if it is wrapped
    in markdown fences or surrounded by stray text.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text, flags=re.I).strip("`").strip()

    # Attempt direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first {...} block
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not parse JSON from GPT response: {text[:200]}")


_REQUIRED_KEYS = {"role", "company", "location", "skills", "salary", "description", "apply_link"}
_DEFAULTS = {
    "role": "Software Developer",
    "company": "Unknown Company",
    "location": "Remote",
    "skills": "Not specified",
    "salary": "Not disclosed",
    "description": "No description available.",
    "apply_link": "N/A",
}


def _validate_and_fill(data: dict[str, Any], raw_job: dict[str, str]) -> dict[str, str]:
    """Ensure all required keys exist and fall back to raw data where possible."""
    result: dict[str, str] = {}
    for key in _REQUIRED_KEYS:
        value = data.get(key) or ""
        if not str(value).strip() or str(value).strip().lower() in ("n/a", "none", "null", ""):
            # Try to salvage from raw job
            raw_map = {
                "role": "title",
                "apply_link": "apply_link",
                "company": "company",
                "location": "location",
                "skills": "skills",
                "salary": "salary",
                "description": "description",
            }
            raw_value = raw_job.get(raw_map.get(key, ""), "")
            result[key] = str(raw_value).strip() if raw_value and raw_value != "N/A" else _DEFAULTS[key]
        else:
            result[key] = str(value).strip()
    return result


def process_job(raw_job: dict[str, str]) -> dict[str, str] | None:
    """
    Send a single raw job dict to GPT-3.5 Turbo and return a structured dict.

    Returns None if processing fails completely (caller should skip this job).
    """
    try:
        logger.debug("Processing job: %s @ %s", raw_job.get("title"), raw_job.get("company"))

        response = _client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=OPENAI_TEMPERATURE,
            max_tokens=OPENAI_MAX_TOKENS,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": _build_user_prompt(raw_job)},
            ],
        )

        raw_output: str = response.choices[0].message.content or ""
        data = _extract_json(raw_output)
        structured = _validate_and_fill(data, raw_job)

        logger.debug("✅ Structured: %s @ %s", structured["role"], structured["company"])
        return structured

    except openai.RateLimitError:
        logger.error("OpenAI rate limit hit — skipping job: %s", raw_job.get("title"))
    except openai.AuthenticationError:
        logger.error("❌ Invalid OpenAI API key. Check config.py / .env")
        raise   # Re-raise so caller can halt the pipeline
    except Exception as exc:
        logger.error("GPT processing failed for '%s': %s", raw_job.get("title"), exc)

    return None


def process_jobs(raw_jobs: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Process a list of raw job dicts through GPT-3.5 Turbo.

    Returns only successfully structured jobs.
    Silently skips any job that fails AI structuring.
    """
    if not raw_jobs:
        logger.warning("No raw jobs provided to process.")
        return []

    structured: list[dict[str, str]] = []
    total = len(raw_jobs)
    logger.info("🤖 Starting AI structuring for %d jobs …", total)

    for idx, job in enumerate(raw_jobs, start=1):
        logger.info("  [%d/%d] %s", idx, total, job.get("title", "Unknown"))
        result = process_job(job)
        if result:
            structured.append(result)

    logger.info("✅ AI structuring done — %d/%d jobs processed successfully", len(structured), total)
    return structured
