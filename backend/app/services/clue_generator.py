"""Per-lesson listening-clue generation (pass four).

Pass one writes the course skeleton, pass two writes the lesson body, pass three
draws the pictures, and this writes the descriptions the aural drill speaks. It
runs after enrichment, on the same lazy-and-cached model, and the result lands in
`lessons.clues_json`.

Why this is not part of the enrichment prompt. The clue is the one piece of
generated text whose correctness is *negative* — it is defined by a sentence it
must not contain — and that is not a property a prompt can promise. It needs a
checker (`app.clue_spec.py`) and a place to retry, which is exactly what a
separate call provides. Folding it into enrichment would also mean that a leaked
clue, or a model that ignored the field, put the entire lesson body at risk of
failing validation, and that regenerating a clue would churn the body and orphan
the diagram drawn from it.

Why it is not derived from the stored definition. The definition is written for a
reader who does not yet know the term, so it names the term and explains it. That
is the right shape for teaching and the wrong shape for testing: the drill needs a
description the learner must match against the options, which is why the clue is
reformulated rather than reused. The definition is an input to this call, never
its output.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from sqlalchemy.orm import Session

from app.clue_spec import validate_clues
from app.services.content_parser import parse_lesson_body
from app.services.llm_json import extract_json_object

if TYPE_CHECKING:
    from app.models import Lesson

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
# Shorter than enrichment's 180s: the output is a handful of sentences rather
# than a full lesson body. Transport failures are not retried, so this is a
# ceiling on the slow path, not a per-attempt budget.
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_CLUE_TIMEOUT_SECONDS", "120"))
# Set explicitly for the same reason lesson_enricher and diagram_generator set
# it: Ollama's runtime default counts prompt and generation in one ~2048-token
# window regardless of the model's advertised context.
CLUE_NUM_CTX = int(os.environ.get("OLLAMA_CLUE_NUM_CTX", "8192"))
CLUE_NUM_PREDICT = int(os.environ.get("OLLAMA_CLUE_NUM_PREDICT", "900"))

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_CLUE_TEMPLATE: str = (_PROMPTS_DIR / "lesson_clues.txt").read_text()

_CLUE_SYSTEM = (
    "You are an expert teacher writing listening-drill clues. A clue describes "
    "one concept so that a listener can identify it, while never writing the "
    "concept's own name — not the term, not a plural or other form of it, not "
    "its acronym, and not the names of the lesson's other concepts. You output "
    "ONLY a valid JSON object matching the schema in the user message — no "
    "markdown, no prose, no code fences. You write plain spoken sentences that "
    "read well aloud."
)

# How much of each concept to show the model. The definition is the grounding —
# the clue must describe this exact mechanism — and it is truncated because the
# instruction forbidding its reuse does not live in the definition's tail.
MAX_CONCEPTS_IN_PROMPT = 6
MAX_DEFINITION_CHARS = 400

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def clue_lock(lesson_id: str) -> threading.Lock:
    """Return the clue lock for a lesson, creating it on first use.

    Separate from lesson_enricher's and diagram_generator's locks: these are
    different calls guarding different columns, and sharing one would make an
    unrelated generation serialise behind another.
    """
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(lesson_id, threading.Lock())


def _concepts_block(lesson: "Lesson") -> str:
    """The lesson's key concepts, as the grounding for the clues."""
    parsed = parse_lesson_body(lesson.content_json or "")
    lines: list[str] = []
    for concept in parsed["key_concepts"][:MAX_CONCEPTS_IN_PROMPT]:
        definition = concept["definition"][:MAX_DEFINITION_CHARS]
        lines.append(f"- {concept['name']}: {definition}")
    return "\n".join(lines) or "(no structured content available)"


def _concept_names(lesson: "Lesson") -> list[str]:
    parsed = parse_lesson_body(lesson.content_json or "")
    return [
        concept["name"]
        for concept in parsed["key_concepts"][:MAX_CONCEPTS_IN_PROMPT]
        if concept["name"]
    ]


def _build_prompt(lesson: "Lesson") -> str:
    try:
        course = lesson.module.course
        course_goal = course.goal
        course_category = course.category
    except AttributeError:
        course_goal = course_category = "(unknown)"

    return _CLUE_TEMPLATE.format(
        course_goal=course_goal,
        course_category=course_category,
        lesson_title=lesson.title,
        lesson_description=lesson.description or "(no summary provided)",
        concepts_block=_concepts_block(lesson),
    )


def _call_ollama(prompt: str) -> str:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{_CLUE_SYSTEM}\n\n{prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "num_ctx": CLUE_NUM_CTX,
            "num_predict": CLUE_NUM_PREDICT,
            # Slightly above the diagram call's 0.2, below enrichment's 0.4.
            # Phrasing benefits from some freedom — the same fact described two
            # ways is what makes a drill feel written rather than templated — but
            # the constraint being satisfied here is hard, and high temperature
            # is what breaks a hard constraint.
            "temperature": 0.3,
        },
    }
    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def generate_clues(lesson: "Lesson") -> dict[str, str]:
    """Generate listening clues for one lesson. Retries once on unusable output.

    Raises RuntimeError if the lesson has no concepts, if both attempts fail, or
    if Ollama is unreachable.
    """
    names = _concept_names(lesson)
    if not names:
        raise RuntimeError("Cannot write listening clues for a lesson with no concepts.")

    prompt = _build_prompt(lesson)

    for attempt in range(1, 3):
        try:
            raw = _call_ollama(prompt)
            return validate_clues(extract_json_object(raw), names)
        except (ValueError, KeyError, TypeError) as exc:
            # Pydantic's ValidationError and JSONDecodeError both subclass
            # ValueError, so a malformed response and a leaky clue land here
            # together — which is right, since the answer to each is a retry.
            logger.warning("Clue attempt %d for lesson %s: %s", attempt, lesson.id, exc)
            if attempt == 2:
                raise RuntimeError(
                    "Clue generation failed after 2 attempts: "
                    "the model did not return usable clues."
                ) from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError(f"Ollama returned HTTP {exc.response.status_code}.") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"Cannot reach Ollama at {OLLAMA_BASE_URL}: {exc}") from exc

    raise RuntimeError("generate_clues: unexpected exit from retry loop")


def ensure_clues(lesson: "Lesson", db: Session) -> dict[str, str] | None:
    """Return this lesson's clues, generating and caching them if absent.

    Never raises. On failure `clues_json` stays NULL so the next open retries
    cleanly — the same bargain `ensure_enriched` makes. There is deliberately no
    cached-empty state: unlike a diagram, which a lesson may legitimately not
    need, every key concept is describable, so "no clues" always means the
    attempt failed and is worth retrying rather than remembering.
    """
    if lesson.clues_json is not None:
        return lesson.clues

    try:
        clues = generate_clues(lesson)
    except RuntimeError as exc:
        logger.error("Clue generation failed for lesson %s: %s", lesson.id, exc)
        return None

    # ensure_ascii=False keeps accented Spanish clues readable in the DB.
    lesson.clues_json = json.dumps({"clues": clues}, ensure_ascii=False)
    db.commit()
    return clues
