import json
import logging
import os
from typing import Any

import httpx

from agents.main import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "120"))

_DURATION_GUIDANCE = {
    "short_term": {
        "label": "2 weeks",
        "module_count": "exactly 2",
        "lessons_per_module": "3 to 4",
    },
    "long_term": {
        "label": "3 months",
        "module_count": "8 to 10",
        "lessons_per_module": "3 to 5",
    },
}


def _build_user_prompt(goal: str, duration: str, category: str) -> str:
    guidance = _DURATION_GUIDANCE[duration]
    return f"""Create a complete course plan for the following learning goal.

Goal: {goal}
Category: {category}
Duration: {guidance["label"]} ({duration.replace("_", " ")})

Requirements:
- The course runs for {guidance["label"]}.
- Include {guidance["module_count"]} modules.
- Each module must have {guidance["lessons_per_module"]} lessons.
- Each lesson must have 2 to 4 learning objectives.
- lesson duration_minutes must be a realistic integer (e.g., 30, 45, 60).

Output ONLY this JSON structure — no other text:

{{
  "title": "Course title here",
  "description": "One or two sentence course overview.",
  "modules": [
    {{
      "title": "Module title",
      "description": "What this module covers.",
      "lessons": [
        {{
          "title": "Lesson title",
          "description": "What this lesson covers.",
          "duration_minutes": 45,
          "objectives": [
            "Objective one.",
            "Objective two.",
            "Objective three."
          ]
        }}
      ]
    }}
  ]
}}

Remember: output ONLY the JSON. No markdown. No extra text."""


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


def _parse_llm_response(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc


def _validate_structure(parsed: dict[str, Any]) -> None:
    required = {"title", "description", "modules"}
    if not required.issubset(parsed.keys()):
        raise ValueError(f"LLM response missing keys: {required - parsed.keys()}")
    if not isinstance(parsed["modules"], list) or len(parsed["modules"]) == 0:
        raise ValueError("LLM response has empty or non-list 'modules'")


def generate_course(goal: str, duration: str, category: str) -> dict[str, Any]:
    """Call Ollama and return a validated course dict. Retries once on bad JSON.

    Raises RuntimeError (→ HTTP 503) if both attempts fail or Ollama is unreachable.
    """
    prompt = _build_user_prompt(goal, duration, category)

    for attempt in range(1, 3):
        try:
            raw = _call_ollama(prompt)
            parsed = _parse_llm_response(raw)
            _validate_structure(parsed)
            return parsed
        except (ValueError, KeyError) as exc:
            logger.warning("Attempt %d: bad LLM response — %s", attempt, exc)
            if attempt == 2:
                raise RuntimeError(
                    "Course generation failed after 2 attempts: LLM did not return valid JSON."
                ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc

    raise RuntimeError("generate_course: unexpected exit from retry loop")
