"""Question generation service.

Follows the same pattern as agents/course_agent.py: build a prompt,
call Ollama with format='json', parse + validate, retry once on bad JSON.
"""

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

from agents.main import SYSTEM_PROMPT

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))


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
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "format": "json",
        "stream": False,
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def _parse_response(raw: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
    # Ollama's format=json sometimes wraps an array in {"questions": [...]}
    if isinstance(parsed, dict):
        for key in ("questions", "items", "data"):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
    return parsed


def _validate_structure(parsed: list[dict[str, Any]]) -> None:
    if not isinstance(parsed, list) or len(parsed) == 0:
        raise ValueError("LLM response is not a non-empty list")
    required = {"question", "reference_answer"}
    if not required.issubset(parsed[0].keys()):
        raise ValueError(f"First item missing keys: {required - parsed[0].keys()}")


def generate_questions(lesson: "Lesson") -> list[dict[str, Any]]:
    """Call Ollama and return a validated list of question dicts.

    Retries once on bad JSON. Raises RuntimeError (→ HTTP 503) on both failures.
    """
    prompt = _build_prompt(lesson)

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
