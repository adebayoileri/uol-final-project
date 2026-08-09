"""Parse structured lesson content from LLM output.

The new course-generation prompt asks the model to embed rich fields in each
lesson JSON: key_concepts, worked_example, common_pitfalls, practice_prompts.
This module extracts those fields from whatever the LLM actually returned,
degrading gracefully when fields are absent or malformed.

Usage:
    from app.services.content_parser import parse_lesson_body
    parsed = parse_lesson_body(lesson.description)
    # Always returns a dict — missing fields are None or [].
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _clean_concept(raw: Any) -> dict | None:
    if not isinstance(raw, dict):
        return None
    return {
        "name": str(raw.get("name", "")).strip(),
        "definition": str(raw.get("definition", "")).strip(),
        "example": str(raw.get("example", "")).strip(),
    }


def parse_lesson_body(raw: str) -> dict:
    """Extract structured fields from a lesson description string.

    Returns a dict with keys:
        key_concepts: list[dict{name, definition, example}] | []
        worked_example: str | None
        common_pitfalls: list[str] | []
        practice_prompts: list[str] | []
        is_structured: bool  — True if the raw string was parseable JSON

    Never raises. All extraction failures are logged at WARNING level.
    """
    result: dict = {
        "key_concepts": [],
        "worked_example": None,
        "common_pitfalls": [],
        "practice_prompts": [],
        "is_structured": False,
    }

    if not raw or not raw.strip():
        return result

    # Only attempt JSON parse if it looks like JSON
    stripped = raw.strip()
    if not stripped.startswith("{"):
        return result

    try:
        data = json.loads(stripped)
    except json.JSONDecodeError as exc:
        logger.warning("content_parser: JSON decode failed: %s", exc)
        return result

    result["is_structured"] = True

    # key_concepts
    raw_concepts = data.get("key_concepts")
    if isinstance(raw_concepts, list):
        cleaned = [_clean_concept(c) for c in raw_concepts]
        result["key_concepts"] = [c for c in cleaned if c and c["name"]]
    elif raw_concepts is not None:
        logger.warning("content_parser: key_concepts is not a list: %r", type(raw_concepts))

    # worked_example
    we = data.get("worked_example")
    if isinstance(we, str) and we.strip():
        result["worked_example"] = we.strip()
    elif we is not None:
        logger.warning("content_parser: worked_example is not a string: %r", type(we))

    # common_pitfalls
    raw_pitfalls = data.get("common_pitfalls")
    if isinstance(raw_pitfalls, list):
        result["common_pitfalls"] = [str(p).strip() for p in raw_pitfalls if str(p).strip()]
    elif raw_pitfalls is not None:
        logger.warning("content_parser: common_pitfalls is not a list: %r", type(raw_pitfalls))

    # practice_prompts
    raw_prompts = data.get("practice_prompts")
    if isinstance(raw_prompts, list):
        result["practice_prompts"] = [str(p).strip() for p in raw_prompts if str(p).strip()]
    elif raw_prompts is not None:
        logger.warning("content_parser: practice_prompts is not a list: %r", type(raw_prompts))

    return result
