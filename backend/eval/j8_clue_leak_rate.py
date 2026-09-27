"""J8 — Does the listening drill's audio give away its own answer?

The defect this measures is simple to state and was invisible to every other
check in the project: the aural drill spoke each concept's stored *definition*
aloud, and a definition opens by naming the term it defines ("Overfitting is
when…"). So the clip announced the answer, and the drill tested nothing.

Two numbers, over the lessons actually in the database:

  1. DEFINITION leak rate — the baseline. The share of key concepts whose
     stored definition contains the concept's own name, in any form. This is
     what the audio used to say, so it is the size of the defect.
  2. CLUE leak rate — the same measurement over the descriptions the drill
     speaks now. It must be zero: `app.clue_spec.py` rejects a leaking clue at
     generation time, so a non-zero value here means the check has a hole.

Coverage is reported alongside them because a leak rate over three clues would
otherwise flatter the result. A course whose lessons have never had the clue
pass reports as uncovered, not as clean.

Reads the database only — no model, no server.

Usage:  cd backend && uv run python -m eval.j8_clue_leak_rate
"""

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.clue_spec import mentioned_name  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models import Lesson, Module  # noqa: E402
from app.services.content_parser import parse_lesson_body  # noqa: E402

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)


def _concepts(lesson: Lesson):
    return [
        c
        for c in parse_lesson_body(lesson.content_json or "")["key_concepts"]
        if c["name"]
    ]


def run() -> dict:
    db = SessionLocal()
    per_course: dict[str, dict] = {}

    try:
        lessons = (
            db.query(Lesson)
            .join(Module, Module.id == Lesson.module_id)
            .filter(Lesson.content_json.isnot(None))
            .all()
        )

        definitions = clues = 0
        definition_leaks = clue_leaks = 0
        clue_lengths: list[int] = []
        courses_without_clues: set[str] = set()

        for lesson in lessons:
            course = lesson.module.course if lesson.module else None
            course_title = course.title if course else "(no course)"
            bucket = per_course.setdefault(
                course_title,
                {"lessons": 0, "concepts": 0, "clues": 0, "definition_leaks": 0, "clue_leaks": 0},
            )
            stored_clues = lesson.clues or {}
            bucket["lessons"] += 1

            for concept in _concepts(lesson):
                name = concept["name"]
                bucket["concepts"] += 1

                # The baseline: what the drill used to speak.
                definitions += 1
                if mentioned_name(concept["definition"], name) is not None:
                    definition_leaks += 1
                    bucket["definition_leaks"] += 1

                clue = stored_clues.get(name.casefold())
                if clue:
                    clues += 1
                    bucket["clues"] += 1
                    clue_lengths.append(len(clue))
                    if mentioned_name(clue, name) is not None:
                        clue_leaks += 1
                        bucket["clue_leaks"] += 1
                else:
                    courses_without_clues.add(course_title)

        def rate(numerator: int, denominator: int) -> float:
            return round(numerator / denominator, 3) if denominator else 0.0

        summary = {
            "timestamp": datetime.now().isoformat(),
            "lessons": len(lessons),
            "per_course": per_course,
            "aggregate": {
                # The size of the defect, on the same content the drill speaks.
                "definition_leak_rate": rate(definition_leaks, definitions),
                "definition_leaks": definition_leaks,
                # Must be 0.0: a non-zero value means the validator has a hole.
                "clue_leak_rate": rate(clue_leaks, clues),
                "clue_leaks": clue_leaks,
                "clue_coverage": rate(clues, definitions),
                "concepts": definitions,
                "concepts_with_clues": clues,
                "courses_missing_clues": sorted(courses_without_clues),
                "clue_chars_mean": round(statistics.mean(clue_lengths)) if clue_lengths else 0,
                "clue_chars_median": round(statistics.median(clue_lengths)) if clue_lengths else 0,
            },
        }
    finally:
        db.close()

    agg = summary["aggregate"]
    print(f"\nLessons with generated content: {agg['concepts']} concepts across {summary['lessons']} lessons")
    print(f"  DEFINITION leak rate (what the audio used to say): {agg['definition_leak_rate']:.1%}"
          f"  ({agg['definition_leaks']}/{agg['concepts']})")
    print(f"  CLUE leak rate       (what the audio says now):   {agg['clue_leak_rate']:.1%}"
          f"  ({agg['clue_leaks']}/{agg['concepts_with_clues']} clues)")
    print(f"  Clue coverage:                                    {agg['clue_coverage']:.1%}"
          f"  ({agg['concepts_with_clues']}/{agg['concepts']} concepts)")
    if agg["clue_chars_mean"]:
        print(f"  Clue length: mean {agg['clue_chars_mean']} chars, median {agg['clue_chars_median']}")
    if agg["courses_missing_clues"]:
        print(f"  Clues incomplete for: {', '.join(agg['courses_missing_clues'])}")
        print("  Run: uv run python -m scripts.backfill_lesson_clues")
    if agg["clue_leaks"]:
        print("\n  FAIL — a stored clue names its own term; the validator let one through.")

    out_path = RESULTS_DIR / f"j8_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nResults written to {out_path}")
    return summary


if __name__ == "__main__":
    run()
