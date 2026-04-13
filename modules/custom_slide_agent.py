from __future__ import annotations

import os
import json
import logging
import traceback
from typing import List, Optional

# ─────────────────────────────────────────────
# Logger
# ─────────────────────────────────────────────
try:
    from utils.logger import logger
except ImportError:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("custom_slide_agent")

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = "gpt-3.5-turbo-1106"
TEMPERATURE    = 0.1
MAX_TOKENS     = 1200

# ─────────────────────────────────────────────
# NEW 3-SLIDE STRUCTURE
# ─────────────────────────────────────────────
SLIDE_SCHEMA = [
    {
        "slide_num": 1,
        "type": "content",
        "title_template": "{topic}",
        "instruction": "Definition + key points combined (5–6 bullets)"
    },
    {
        "slide_num": 2,
        "type": "real_world_use",
        "title_template": "Real-World Use Cases",
        "instruction": "4–5 real-world applications"
    },
    {
        "slide_num": 3,
        "type": "interview_questions",
        "title_template": "Interview Questions 🎯",
        "instruction": "4–5 common interview questions"
    },
]

# ─────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────
def _build_system_prompt():
    return (
        "You are an expert CS educator creating Instagram slides.\n\n"
        "RULES:\n"
        "- Output ONLY JSON\n"
        "- Use bullet points starting with •\n"
        "- Max 6 bullets per slide\n"
        "- Each bullet <= 15 words\n"
        "- No paragraphs\n"
    )


def _build_user_prompt(topic: str, context: Optional[str]):
    schema_desc = "\n".join(
        f"Slide {s['slide_num']}: {s['instruction']}"
        for s in SLIDE_SCHEMA
    )

    context_block = ""
    if context:
        context_block = f"\nUse this reference:\n{context[:1500]}\n"

    return f"""
Generate EXACTLY 3 slides for topic: {topic}

{context_block}

Structure:
{schema_desc}

Return ONLY JSON ARRAY like:
[
  {{
    "title": "{topic}",
    "content": ["• point1", "• point2"],
    "type": "content"
  }},
  ...
]

NO markdown. NO explanation.
"""


# ─────────────────────────────────────────────
# OpenAI Call
# ─────────────────────────────────────────────
def _call_openai(system_prompt, user_prompt):
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )

    return response.choices[0].message.content


# ─────────────────────────────────────────────
# Parser (FIXED 🔥)
# ─────────────────────────────────────────────
def _parse_slides(raw: str, topic: str):
    try:
        cleaned = raw.strip()

        # Remove markdown if present
        if cleaned.startswith("```"):
            cleaned = "\n".join(
                line for line in cleaned.splitlines()
                if not line.startswith("```")
            )

        data = json.loads(cleaned)

        if isinstance(data, dict):
            data = list(data.values())[0]

        if not isinstance(data, list):
            raise ValueError("Not a list")

        slides = []
        for i, item in enumerate(data[:3]):
            slides.append({
                "title": item.get("title", topic),
                "content": item.get("content", []),
                "type": item.get("type", SLIDE_SCHEMA[i]["type"]),
            })

        return slides

    except Exception as e:
        logger.error(f"Parse failed: {e}")
        return _fallback_slides(topic)


# ─────────────────────────────────────────────
# Fallback (UPDATED)
# ─────────────────────────────────────────────
def _fallback_slides(topic: str):
    return [
        {
            "title": topic,
            "content": [
                f"• {topic} is an important concept",
                "• Used in many applications",
                "• Improves efficiency",
                "• Easy to understand basics",
            ],
            "type": "content",
        },
        {
            "title": "Real-World Use Cases",
            "content": [
                "• Used in web apps",
                "• Used in data processing",
                "• Used in AI systems",
            ],
            "type": "real_world_use",
        },
        {
            "title": "Interview Questions 🎯",
            "content": [
                f"1. What is {topic}?",
                "2. Where is it used?",
                "3. Advantages?",
            ],
            "type": "interview_questions",
        },
    ]


# ─────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────
def generate_custom_slides(topic: str, context: Optional[str] = None):
    if not topic:
        return _fallback_slides("Unknown")

    mode = "RAG" if context else "General"
    logger.info(f"{mode} mode for {topic}")

    try:
        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(topic, context)

        raw = _call_openai(system_prompt, user_prompt)

        slides = _parse_slides(raw, topic)

        logger.info(f"Generated {len(slides)} slides")
        return slides

    except Exception as e:
        logger.error(e)
        return _fallback_slides(topic)


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────
if __name__ == "__main__":
    slides = generate_custom_slides("Python")
    print(slides)