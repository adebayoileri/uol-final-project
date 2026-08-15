"""Question generation service.

Follows the same pattern as agents/course_agent.py: build a prompt,
call Ollama (no format=json — that mode forces a single object and breaks arrays),
extract the JSON array from raw text, validate, retry once on bad JSON.
"""

import json  # still used in _parse_response
import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from agents.main import SYSTEM_PROMPT
from app.services.content_parser import parse_lesson_body

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

_OPEN_TEMPLATE: str = (_PROMPTS_DIR / "question_open.txt").read_text()
_FILL_BLANK_TEMPLATE: str = (_PROMPTS_DIR / "question_fill_blank.txt").read_text()


def _is_python_lesson(lesson: "Lesson") -> bool:
    try:
        return lesson.module.course.category.lower() == "python"
    except AttributeError:
        return False


def _build_context_blocks(lesson: "Lesson") -> dict[str, str]:
    """Build template substitution dict from lesson, enriched with parsed structured content."""
    objectives_block = "\n".join(
        f"- {obj.description}" for obj in lesson.objectives
    ) or "- (no objectives listed)"

    # Structured content lives in content_json; `description` stays prose
    # because it is passed into the prompt verbatim below.
    parsed = parse_lesson_body(lesson.content_json or "")

    key_concepts_block = ""
    if parsed["key_concepts"]:
        lines = ["Key concepts:"] + [
            f"- {c['name']}: {c['definition']}" for c in parsed["key_concepts"][:4]
        ]
        key_concepts_block = "\n".join(lines)

    practice_prompts_block = ""
    if parsed["practice_prompts"]:
        lines = ["Practice prompt seeds (use as inspiration, not verbatim):"] + [
            f"- {p}" for p in parsed["practice_prompts"][:3]
        ]
        practice_prompts_block = "\n".join(lines)

    return {
        "lesson_title": lesson.title,
        "lesson_description": lesson.description if len(lesson.description) < 500
                              else lesson.description[:500] + "…",
        "objectives_block": objectives_block,
        "key_concepts_block": key_concepts_block,
        "practice_prompts_block": practice_prompts_block,
    }


def _build_python_prompt(lesson: "Lesson") -> str:
    return _FILL_BLANK_TEMPLATE.format(**_build_context_blocks(lesson))


def _build_prompt(lesson: "Lesson") -> str:
    return _OPEN_TEMPLATE.format(**_build_context_blocks(lesson))


def _call_ollama(prompt: str) -> str:
    # No format="json": that mode coerces output into a single object, breaking top-level arrays.
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": False,
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def _parse_response(raw: str) -> list[dict[str, Any]]:
    # Strip markdown fences (```json ... ``` or ``` ... ```)
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()

    # Extract the first complete JSON array from the text.
    start = raw.find("[")
    if start != -1:
        depth = 0
        for i, ch in enumerate(raw[start:], start):
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(raw[start : i + 1])
                    except json.JSONDecodeError:
                        break

    # Fallback: try parsing the whole string as JSON
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    if isinstance(parsed, dict):
        for value in parsed.values():
            if isinstance(value, list):
                return value

    return parsed


def _validate_structure(parsed: list[dict[str, Any]]) -> None:
    if not isinstance(parsed, list) or len(parsed) == 0:
        raise ValueError("LLM response is not a non-empty list")
    required = {"question", "reference_answer"}
    if not required.issubset(parsed[0].keys()):
        raise ValueError(f"First item missing keys: {required - parsed[0].keys()}")
    for item in parsed:
        if item.get("question_type") == "fill_blank" and "code_snippet" not in item:
            raise ValueError("fill_blank item missing code_snippet")


def generate_questions(lesson: "Lesson") -> list[dict[str, Any]]:
    """Call Ollama and return a validated list of question dicts.

    Retries once on bad JSON. Raises RuntimeError (→ HTTP 503) on both failures.
    """
    prompt = _build_python_prompt(lesson) if _is_python_lesson(lesson) else _build_prompt(lesson)

    for attempt in range(1, 3):
        try:
            raw = _call_ollama(prompt)
            parsed = _parse_response(raw)
            _validate_structure(parsed)
            return parsed
        except (ValueError, KeyError) as exc:
            logger.warning("Attempt %d: bad LLM response — %s", attempt, exc)
            if attempt == 2:
                raise RuntimeError(
                    "Question generation failed after 2 attempts: LLM did not return valid JSON."
                ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc

    raise RuntimeError("generate_questions: unexpected exit from retry loop")
