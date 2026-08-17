"""Per-lesson diagram generation (pass three).

Pass one writes the course skeleton, pass two writes the lesson body, and this
writes the pictures. It runs after enrichment, on the same lazy-and-cached
model, and the result lands in `lessons.diagram_json`.

Kept as a separate call rather than four more fields on the enrichment prompt
for one evidenced reason: lesson_enricher already carries scars from Ollama's
default context window truncating a body mid-`worked_example`, and a spec for
four diagram kinds is a substantially longer prompt again. Folding it in would
put working lesson content at risk to save a call. Here, the worst case is a
lesson with no diagram — which is exactly what most lessons should have anyway.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy.orm import Session

from app.diagram_spec import validate_diagrams
from app.services.content_parser import parse_lesson_body
from app.services.llm_json import extract_json_object

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_DIAGRAM_TIMEOUT_SECONDS", "150"))
# Set explicitly for the same reason lesson_enricher sets it: Ollama's runtime
# default counts prompt and generation in one ~2048-token window regardless of
# the model's advertised context. This prompt alone is over half of that.
DIAGRAM_NUM_CTX = int(os.environ.get("OLLAMA_DIAGRAM_NUM_CTX", "8192"))
DIAGRAM_NUM_PREDICT = int(os.environ.get("OLLAMA_DIAGRAM_NUM_PREDICT", "1536"))

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_DIAGRAM_TEMPLATE: str = (_PROMPTS_DIR / "lesson_diagram.txt").read_text()

_DIAGRAM_SYSTEM = (
    "You are a teacher deciding whether a diagram helps a lesson, and if so "
    "describing it in structured fields. You output ONLY a valid JSON object "
    "matching the schema in the user message — no markdown, no prose, no code "
    "fences. You never output SVG, coordinates or colours. You would rather "
    "return no diagram than a decorative one."
)

# How much of the lesson body to show the model. Enough to ground the diagram in
# what was actually taught, short enough to leave room to answer.
MAX_CONCEPTS_IN_PROMPT = 4
MAX_WORKED_EXAMPLE_CHARS = 900

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def diagram_lock(lesson_id: str) -> threading.Lock:
    """Return the diagram lock for a lesson, creating it on first use.

    Separate from lesson_enricher's lock: these are different calls guarding
    different columns, and sharing one would make an enrichment serialise
    behind an unrelated diagram generation.
    """
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(lesson_id, threading.Lock())


def _content_block(lesson: "Lesson") -> str:
    """Summarise the enriched body so the diagram illustrates real material."""
    parsed = parse_lesson_body(lesson.content_json or "")
    lines: list[str] = []

    for concept in parsed["key_concepts"][:MAX_CONCEPTS_IN_PROMPT]:
        lines.append(f"- {concept['name']}: {concept['definition']}")
        if concept["example"]:
            lines.append(f"  example: {concept['example']}")

    worked = parsed["worked_example"]
    if worked:
        lines.append("")
        lines.append(f"Worked example: {worked[:MAX_WORKED_EXAMPLE_CHARS]}")

    return "\n".join(lines) or "(no structured content available)"


def _build_prompt(lesson: "Lesson") -> str:
    try:
        course = lesson.module.course
        course_goal = course.goal
        course_category = course.category
    except AttributeError:
        course_goal = course_category = "(unknown)"

    return _DIAGRAM_TEMPLATE.format(
        course_goal=course_goal,
        course_category=course_category,
        lesson_title=lesson.title,
        lesson_description=lesson.description or "(no summary provided)",
        content_block=_content_block(lesson),
    )


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{_DIAGRAM_SYSTEM}\n\n{prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "num_ctx": DIAGRAM_NUM_CTX,
            "num_predict": DIAGRAM_NUM_PREDICT,
            # Lower than enrichment's 0.4. This call picks from a fixed menu of
            # kinds and fills factual fields; there is nothing here that
            # benefits from variety, and plenty that breaks under it.
            "temperature": 0.2,
        },
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def generate_diagrams(lesson: "Lesson") -> list[dict[str, Any]]:
    """Generate diagram specs for one lesson. Retries once on unusable output.

    An empty list is a legitimate result, not a failure — see DiagramSet.
    Raises RuntimeError if both attempts fail or Ollama is unreachable.
    """
    prompt = _build_prompt(lesson)

    for attempt in range(1, 3):
        try:
            raw = _call_ollama(prompt)
            return validate_diagrams(extract_json_object(raw))
        except (ValueError, KeyError, TypeError) as exc:
            # Pydantic's ValidationError and JSONDecodeError both subclass
            # ValueError, so a malformed response and an invalid spec land here
            # together — which is right, since the response to each is a retry.
            logger.warning(
                "Diagram attempt %d for lesson %s: %s", attempt, lesson.id, exc
            )
            if attempt == 2:
                raise RuntimeError(
                    "Diagram generation failed after 2 attempts: "
                    "the model did not return a usable specification."
                ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(
                f"Ollama returned HTTP {exc.response.status_code}."
            ) from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc

    raise RuntimeError("generate_diagrams: unexpected exit from retry loop")


def ensure_diagrams(lesson: "Lesson", db: Session) -> list[dict[str, Any]] | None:
    """Return this lesson's diagrams, generating and caching them if absent.

    Never raises. Three states are distinguishable on purpose:
      diagram_json IS NULL  -> never attempted, or the last attempt failed
      diagram_json = '[]'   -> attempted, and the model correctly declined
      otherwise             -> has diagrams
    Without the middle state a lesson that genuinely needs no diagram would pay
    for a generation call on every single open, forever.
    """
    if lesson.diagram_json is not None:
        return lesson.diagrams

    try:
        diagrams = generate_diagrams(lesson)
    except RuntimeError as exc:
        logger.error("Diagram generation failed for lesson %s: %s", lesson.id, exc)
        return None

    lesson.diagram_json = json.dumps(diagrams, ensure_ascii=False)
    db.commit()
    return diagrams
