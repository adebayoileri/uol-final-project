"""Per-lesson deep content generation (pass two of course generation).

Course generation produces the skeleton — titles, a prose summary, objectives.
This module produces the body a learner actually reads: key concepts with real
examples, a multi-step worked example, pitfalls and practice prompts. It runs
once per lesson, on first open, and the result is cached in
`lessons.content_json`.

Splitting it out of course generation is what makes depth possible: a single
call asking for every lesson in a course has to ration its output across up to
50 lessons, and the result was a two-sentence placeholder per lesson.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy.orm import Session

from app.services.content_parser import parse_lesson_body

# Shared with diagram_generator. Re-exported under the original private name so
# the existing tests that pin this scanner's behaviour keep importing it here.
from app.services.llm_json import extract_json_object as _extract_object

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
# Longer than the shared 120s: this call generates roughly 4x the tokens of a
# question-generation call. Transport failures are not retried, so this is a
# hard ceiling on the slow path rather than a per-attempt budget.
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_ENRICH_TIMEOUT_SECONDS", "180"))
ENRICH_NUM_CTX = int(os.environ.get("OLLAMA_ENRICH_NUM_CTX", "8192"))
ENRICH_NUM_PREDICT = int(os.environ.get("OLLAMA_ENRICH_NUM_PREDICT", "2048"))

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_LESSON_CONTENT_TEMPLATE: str = (_PROMPTS_DIR / "lesson_content.txt").read_text()

# agents.main.SYSTEM_PROMPT casts the model as a curriculum designer producing a
# course plan — the wrong role for writing one lesson's body.
_ENRICH_SYSTEM = (
    "You are an expert subject-matter teacher writing the body of a single lesson. "
    "You output ONLY a valid JSON object matching the schema in the user message — "
    "no markdown, no prose, no code fences. "
    "You write specific, concrete teaching material: real examples with real values, "
    "never placeholders and never restatements of the lesson summary."
)

# The anti-shallowness gate. Without these thresholds a model can satisfy the
# schema with one-line definitions and the original problem returns.
MIN_CONCEPTS = 2
MIN_DEFINITION_CHARS = 60
MIN_WORKED_EXAMPLE_CHARS = 200

# Per-lesson locks so two concurrent opens don't both pay for generation.
_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def lesson_lock(lesson_id: str) -> threading.Lock:
    """Return the lock for a lesson, creating it on first use.

    In-process only. Under multiple uvicorn workers two processes could still
    race; the `content_json IS NULL` check keeps the worst case a wasted call
    rather than corruption.
    """
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(lesson_id, threading.Lock())


def _build_prompt(lesson: "Lesson") -> str:
    objectives_block = (
        "\n".join(f"- {o.description}" for o in lesson.objectives)
        or "- (no objectives listed)"
    )
    try:
        course = lesson.module.course
        course_goal = course.goal
        course_category = course.category
        module_title = lesson.module.title
    except AttributeError:
        course_goal = course_category = module_title = "(unknown)"

    return _LESSON_CONTENT_TEMPLATE.format(
        course_goal=course_goal,
        course_category=course_category,
        module_title=module_title,
        lesson_title=lesson.title,
        lesson_description=lesson.description or "(no summary provided)",
        objectives_block=objectives_block,
    )


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{_ENRICH_SYSTEM}\n\n{prompt}",
        "format": "json",
        "stream": False,
        # The first explicit options block in this codebase. Ollama's runtime
        # num_ctx default (~2048) counts prompt and generation in one window,
        # regardless of the model's advertised context length — a 1000-1400
        # token body truncates mid-worked_example and burns both retries.
        # num_predict is a ceiling that turns a degenerate repetition loop into
        # a clean rejection instead of a 180s timeout.
        "options": {
            "num_ctx": ENRICH_NUM_CTX,
            "num_predict": ENRICH_NUM_PREDICT,
            "temperature": 0.4,
        },
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def _normalise(obj: dict[str, Any]) -> dict[str, Any]:
    """Clean via parse_lesson_body so stored bytes match what readers parse back.

    Round-tripping through the same parser every consumer uses makes the write
    provably idempotent and keeps concept cleaning in one already-tested place.
    """
    parsed = parse_lesson_body(json.dumps(obj))
    return {
        "key_concepts": parsed["key_concepts"],
        "worked_example": parsed["worked_example"],
        "common_pitfalls": parsed["common_pitfalls"],
        "practice_prompts": parsed["practice_prompts"],
    }


def _validate_content(content: dict[str, Any]) -> None:
    """Reject thin output. key_concepts and worked_example are hard requirements.

    Missing pitfalls or practice prompts are logged but accepted — spending
    another 60-second call to fix a cosmetic gap is not worth it.
    """
    concepts = content["key_concepts"]
    if len(concepts) < MIN_CONCEPTS:
        raise ValueError(f"only {len(concepts)} key_concepts (need >= {MIN_CONCEPTS})")
    if not any(len(c["definition"]) >= MIN_DEFINITION_CHARS for c in concepts):
        raise ValueError("no concept has a substantive definition")

    worked = content["worked_example"] or ""
    if len(worked) < MIN_WORKED_EXAMPLE_CHARS:
        raise ValueError(f"worked_example too short ({len(worked)} chars)")

    if not content["common_pitfalls"]:
        logger.info("enrichment: no common_pitfalls returned (accepted)")
    if not content["practice_prompts"]:
        logger.info("enrichment: no practice_prompts returned (accepted)")


def generate_lesson_content(lesson: "Lesson") -> dict[str, Any]:
    """Generate deep content for one lesson. Retries once on unusable output.

    Raises RuntimeError if both attempts fail or Ollama is unreachable.
    """
    prompt = _build_prompt(lesson)

    for attempt in range(1, 3):
        try:
            raw = _call_ollama(prompt)
            content = _normalise(_extract_object(raw))
            _validate_content(content)
            return content
        except (ValueError, KeyError) as exc:  # JSONDecodeError subclasses ValueError
            logger.warning("Enrich attempt %d for lesson %s: %s", attempt, lesson.id, exc)
            if attempt == 2:
                raise RuntimeError(
                    "Lesson enrichment failed after 2 attempts: "
                    "the model did not return usable content."
                ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc

    raise RuntimeError("generate_lesson_content: unexpected exit from retry loop")


def ensure_enriched(lesson: "Lesson", db: Session) -> dict[str, Any] | None:
    """Return this lesson's content, generating and caching it if absent.

    Never raises. On failure `content_json` stays NULL, so the next open retries
    cleanly — there is no poison-pill state and no partial write.
    """
    if lesson.content_json:
        parsed = parse_lesson_body(lesson.content_json)
        return {k: v for k, v in parsed.items() if k != "is_structured"}

    try:
        content = generate_lesson_content(lesson)
    except RuntimeError as exc:
        logger.error("Enrichment failed for lesson %s: %s", lesson.id, exc)
        return None

    # ensure_ascii=False keeps accented Spanish content readable in the DB.
    lesson.content_json = json.dumps(content, ensure_ascii=False)
    db.commit()
    return content
