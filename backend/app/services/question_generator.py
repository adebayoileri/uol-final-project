"""Question generation service.

Follows the same pattern as agents/course_agent.py: build a prompt,
call Ollama (no format=json — that mode forces a single object and breaks arrays),
extract the JSON array from raw text, validate, retry once on bad JSON.
"""

import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

import httpx

from agents.main import SYSTEM_PROMPT

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))


def _is_python_lesson(lesson: "Lesson") -> bool:
    try:
        return lesson.module.course.category.lower() == "python"
    except AttributeError:
        return False


def _build_python_prompt(lesson: "Lesson") -> str:
    objectives_block = "\n".join(
        f"- {obj.description}" for obj in lesson.objectives
    ) or "- (no objectives listed)"

    return f"""Generate exactly 4 questions for the following Python lesson: 2 open-ended conceptual questions and 2 fill-the-blank code exercises.

Lesson title: {lesson.title}
Lesson description: {lesson.description}
Learning objectives:
{objectives_block}

For each open-ended question use this format:
  {{"question_type": "open", "question": "Question text.", "reference_answer": "1-3 sentence answer."}}

For each fill-the-blank exercise use this format:
  {{"question_type": "fill_blank", "question": "Short instruction describing what to complete.", "code_snippet": "Python code block with exactly ONE line replaced by    # BLANK", "reference_answer": "The exact line that replaces # BLANK, with correct indentation."}}

Rules for fill-the-blank:
- The # BLANK marker replaces exactly one meaningful line of code (not a comment or blank line)
- The reference_answer must be the complete line that goes in place of # BLANK (include indentation)
- Keep snippets short (4-8 lines total). No execution required.
- Do NOT include triple backticks in the code_snippet value

Output ONLY this JSON array — no other text:
[
  {{"question_type": "open", "question": "...", "reference_answer": "..."}},
  {{"question_type": "fill_blank", "question": "...", "code_snippet": "...", "reference_answer": "..."}},
  {{"question_type": "open", "question": "...", "reference_answer": "..."}},
  {{"question_type": "fill_blank", "question": "...", "code_snippet": "...", "reference_answer": "..."}}
]

Remember: output ONLY the JSON array. No markdown. No prose."""


def _build_prompt(lesson: "Lesson") -> str:
    objectives_block = "\n".join(
        f"- {obj.description}" for obj in lesson.objectives
    ) or "- (no objectives listed)"

    return f"""Generate 3 to 5 open-ended questions for the following lesson.
For each question, provide a concise reference answer of 1 to 3 sentences.

Lesson title: {lesson.title}
Lesson description: {lesson.description}
Learning objectives:
{objectives_block}

Output ONLY this JSON array — no other text:
[
  {{
    "question": "Question text here.",
    "reference_answer": "Ideal answer here, 1 to 3 sentences."
  }}
]

Remember: output ONLY the JSON array. No markdown. No prose."""


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
    # The model often prefixes with prose ("Here are the questions:"), so we
    # scan for the opening '[' and walk to its matching ']'.
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
