"""Practice drills derived from enriched lesson content.

Every drill here is built deterministically from `lessons.content_json` — the
key concepts, worked example and examples produced by the enrichment pass. No
LLM call happens when a learner starts a drill, so they are instant, work
offline, and produce the same items for the same content.

The drill set covers the VARK modalities that the read-and-type review loop
does not: MCQ (read/write), match (visual), order (kinesthetic), listen and
pronounce (aural).
"""

import hashlib
import re
import random
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models import Course, Lesson, Module
from app.services.content_parser import parse_lesson_body
from app.services.course_profile import resolve_course_profile

DrillKind = Literal["mcq", "match", "order", "listen", "pronounce"]

DRILL_KINDS: tuple[DrillKind, ...] = ("mcq", "match", "order", "listen", "pronounce")

DRILL_META: dict[DrillKind, dict[str, str]] = {
    "mcq": {
        "title": "Multiple choice",
        "modality": "Read/write",
        "description": "Read a definition, pick the concept it describes.",
    },
    "match": {
        "title": "Concept match",
        "modality": "Visual",
        "description": "Pair each concept with its definition.",
    },
    "order": {
        "title": "Step order",
        "modality": "Kinesthetic",
        "description": "Put the steps of a worked example back in order.",
    },
    "listen": {
        "title": "Listening",
        "modality": "Aural",
        "description": "Hear a definition read aloud, pick the concept.",
    },
    "pronounce": {
        "title": "Pronunciation",
        "modality": "Aural",
        "description": "Say the phrase and compare against what was heard.",
    },
}

# Availability floors. Below these an item set is either impossible or so thin
# it teaches nothing, so the drill is reported unavailable with a reason rather
# than padded with filler.
MIN_MCQ_CONCEPTS = 3
MIN_MATCH_CONCEPTS = 4
MIN_ORDER_STEPS = 3
MAX_MCQ_OPTIONS = 4


@dataclass
class Concept:
    name: str
    definition: str
    example: str
    lesson_id: str
    lesson_title: str


def _stable_rng(seed_material: str) -> random.Random:
    """Deterministic shuffling, so the same content yields the same drill."""
    digest = hashlib.sha256(seed_material.encode()).hexdigest()[:8]
    return random.Random(int(digest, 16))


def load_course_lessons(course_id: str, db: Session) -> list[Lesson]:
    return (
        db.query(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .filter(Module.course_id == course_id)
        .order_by(Lesson.order_index)
        .all()
    )


def collect_concepts(lessons: list[Lesson]) -> list[Concept]:
    """Every key concept across the course's enriched lessons.

    Pooling course-wide rather than per-lesson matters: with only one or two
    lessons enriched, a per-lesson pool routinely cannot field enough
    distractors for a multiple-choice question.
    """
    out: list[Concept] = []
    for lesson in lessons:
        parsed = parse_lesson_body(lesson.content_json or "")
        for concept in parsed["key_concepts"]:
            name = concept.get("name", "").strip()
            definition = concept.get("definition", "").strip()
            if not (name and definition):
                continue
            out.append(
                Concept(
                    name=name,
                    definition=definition,
                    # `example` is legitimately allowed to be empty.
                    example=concept.get("example", "").strip(),
                    lesson_id=lesson.id,
                    lesson_title=lesson.title,
                )
            )
    return out


# A leading "Step 3:" or "3." is how the model marks order, and it is exactly
# what the ordering drill asks the learner to reconstruct. Requiring whitespace
# after a bare number keeps "3.14 is pi" from being read as a marker.
_STEP_MARKER_RE = re.compile(r"^\s*(?:step\s*\d+\s*[:.)\-]\s*|\d+\s*[.)]\s+)", re.IGNORECASE)


def strip_step_marker(step: str) -> str:
    """Remove the ordinal prefix from one step.

    Load-bearing for the ordering drill: with the marker left in, every card
    read "Step 1: …", "Step 2: …" while asking the learner to put them in
    order. The drill was solvable without reading a word of it, which is worse
    than having no drill at all — it looks like practice and tests nothing.
    """
    return _STEP_MARKER_RE.sub("", step, count=1).strip()


def split_steps(worked_example: str) -> list[str]:
    """Split a worked example into steps, without their ordinal markers.

    The enrichment prompt asks for newline-separated steps, but in practice the
    model routinely returns one line of "Step 1: ... Step 2: ...". Splitting on
    newlines alone left every real worked example looking like a single step,
    which made the ordering drill permanently unavailable — so fall back to the
    explicit markers.

    The markers still drive the *split*; they are stripped afterwards. Splitting
    on something and then keeping it were never the same decision.
    """
    if not worked_example:
        return []

    def clean(parts: list[str]) -> list[str]:
        return [stripped for p in parts if (stripped := strip_step_marker(p))]

    steps = [line.strip() for line in worked_example.splitlines() if line.strip()]
    if len(steps) >= MIN_ORDER_STEPS:
        return clean(steps)

    # "Step 1: ..." / "Step 2: ..." run together on one line.
    marked = [s.strip() for s in re.split(r"(?=\bStep\s+\d+\s*[:.])", worked_example) if s.strip()]
    if len(marked) >= MIN_ORDER_STEPS:
        return clean(marked)

    # "1. ... 2. ..." numbered prose.
    numbered = [s.strip() for s in re.split(r"(?=(?:^|\s)\d+\.\s)", worked_example) if s.strip()]
    if len(numbered) >= MIN_ORDER_STEPS:
        return clean(numbered)

    return clean(steps)


def collect_step_sets(lessons: list[Lesson]) -> list[dict[str, Any]]:
    """Worked examples with enough steps to be worth reordering."""
    out: list[dict[str, Any]] = []
    for lesson in lessons:
        parsed = parse_lesson_body(lesson.content_json or "")
        steps = split_steps(parsed["worked_example"] or "")
        if len(steps) < MIN_ORDER_STEPS:
            continue
        out.append({"lesson_id": lesson.id, "lesson_title": lesson.title, "steps": steps})
    return out


def _dedupe_concepts(concepts: list[Concept]) -> list[Concept]:
    seen: set[str] = set()
    out: list[Concept] = []
    for c in concepts:
        key = c.name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def drill_availability(course: Course, lessons: list[Lesson]) -> dict[str, Any]:
    """What this course can currently offer, and why not when it can't."""
    concepts = _dedupe_concepts(collect_concepts(lessons))
    step_sets = collect_step_sets(lessons)
    profile = resolve_course_profile(course)

    enriched = sum(1 for lesson in lessons if lesson.content_json)
    total = len(lessons)
    not_enriched_reason = (
        "Open a lesson to generate its content first"
        if enriched == 0
        else f"Needs more content — only {enriched} of {total} lessons generated so far"
    )

    def entry(kind: DrillKind, available: bool, count: int, reason: str | None):
        return {
            "kind": kind,
            "title": DRILL_META[kind]["title"],
            "modality": DRILL_META[kind]["modality"],
            "description": DRILL_META[kind]["description"],
            "available": available,
            "item_count": count,
            "reason": reason,
        }

    pronounceable = [c for c in concepts if c.example or c.name]

    return {
        "course_id": course.id,
        "course_title": course.title,
        "enriched_lessons": enriched,
        "total_lessons": total,
        "target_language": profile.target_language,
        "drills": [
            entry(
                "mcq",
                len(concepts) >= MIN_MCQ_CONCEPTS,
                len(concepts),
                None if len(concepts) >= MIN_MCQ_CONCEPTS else not_enriched_reason,
            ),
            entry(
                "match",
                len(concepts) >= MIN_MATCH_CONCEPTS,
                len(concepts),
                None if len(concepts) >= MIN_MATCH_CONCEPTS else not_enriched_reason,
            ),
            entry(
                "order",
                len(step_sets) > 0,
                len(step_sets),
                None
                if step_sets
                else (
                    not_enriched_reason
                    if enriched == 0
                    else "No worked example with enough steps yet"
                ),
            ),
            entry(
                "listen",
                len(concepts) >= MIN_MCQ_CONCEPTS,
                len(concepts),
                None if len(concepts) >= MIN_MCQ_CONCEPTS else not_enriched_reason,
            ),
            entry(
                "pronounce",
                profile.is_language_course and bool(pronounceable),
                len(pronounceable) if profile.is_language_course else 0,
                None
                if profile.is_language_course and pronounceable
                else (
                    "Only for language courses"
                    if not profile.is_language_course
                    else not_enriched_reason
                ),
            ),
        ],
    }


# ---------------------------------------------------------------------------
# Item generation
# ---------------------------------------------------------------------------

def _options_for(answer: Concept, pool: list[Concept], rng: random.Random) -> tuple[list[str], int]:
    distractors = [c.name for c in pool if c.name.lower() != answer.name.lower()]
    rng.shuffle(distractors)
    options = [answer.name] + distractors[: MAX_MCQ_OPTIONS - 1]
    rng.shuffle(options)
    return options, options.index(answer.name)


def build_mcq(concepts: list[Concept], n: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = _dedupe_concepts(concepts)
    if len(pool) < MIN_MCQ_CONCEPTS:
        return []
    chosen = pool[:]
    rng.shuffle(chosen)
    items = []
    for concept in chosen[:n]:
        options, answer_index = _options_for(concept, pool, rng)
        items.append(
            {
                "id": f"mcq-{concept.lesson_id}-{concept.name}",
                "prompt": concept.definition,
                "options": options,
                "answer_index": answer_index,
                "lesson_title": concept.lesson_title,
                "example": concept.example or None,
            }
        )
    return items


def build_match(concepts: list[Concept], n: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = _dedupe_concepts(concepts)
    if len(pool) < MIN_MATCH_CONCEPTS:
        return []
    chosen = pool[:]
    rng.shuffle(chosen)
    # Rounds of up to 4 pairs keep each screen readable.
    group = chosen[: max(MIN_MATCH_CONCEPTS, min(n, 6))]
    return [
        {
            "id": f"match-{c.lesson_id}-{c.name}",
            "name": c.name,
            "definition": c.definition,
            "lesson_title": c.lesson_title,
        }
        for c in group
    ]


def build_order(step_sets: list[dict[str, Any]], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Shuffle a worked example's steps.

    `steps` is in display order. `correct_order` holds display indices in the
    sequence they belong, so the client restores the original with
    `[steps[i] for i in correct_order]`.
    """
    items = []
    for entry in step_sets[:n]:
        steps = entry["steps"]
        order = list(range(len(steps)))
        shuffled = order[:]
        # Guarantee the shuffle actually differs, or the drill is a no-op.
        for _ in range(8):
            rng.shuffle(shuffled)
            if shuffled != order:
                break
        items.append(
            {
                "id": f"order-{entry['lesson_id']}",
                "lesson_title": entry["lesson_title"],
                "steps": [steps[i] for i in shuffled],
                "correct_order": [shuffled.index(i) for i in order],
            }
        )
    return items


def build_listen(concepts: list[Concept], n: int, rng: random.Random) -> list[dict[str, Any]]:
    """Same shape as MCQ, but the prompt is spoken rather than shown.

    The definition text is deliberately NOT sent to the client — if it were,
    the learner could read instead of listen and the drill would be pointless.
    """
    items = build_mcq(concepts, n, rng)
    for item in items:
        item["id"] = item["id"].replace("mcq-", "listen-", 1)
        item["speak"] = item.pop("prompt")
        item["example"] = None
    return items


def build_pronounce(concepts: list[Concept], n: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = [c for c in _dedupe_concepts(concepts) if c.example or c.name]
    chosen = pool[:]
    rng.shuffle(chosen)
    return [
        {
            "id": f"pronounce-{c.lesson_id}-{c.name}",
            # Prefer the concrete example, which for a language course is the
            # target-language phrase; fall back to the term itself.
            "phrase": c.example or c.name,
            "concept": c.name,
            "lesson_title": c.lesson_title,
        }
        for c in chosen[:n]
    ]


def build_drill(
    kind: DrillKind, course: Course, lessons: list[Lesson], n: int
) -> list[dict[str, Any]]:
    concepts = collect_concepts(lessons)
    rng = _stable_rng(f"{course.id}:{kind}")

    if kind == "mcq":
        return build_mcq(concepts, n, rng)
    if kind == "match":
        return build_match(concepts, n, rng)
    if kind == "order":
        return build_order(collect_step_sets(lessons), n, rng)
    if kind == "listen":
        return build_listen(concepts, n, rng)
    if kind == "pronounce":
        return build_pronounce(concepts, n, rng)
    return []
