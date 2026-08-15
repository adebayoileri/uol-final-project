"""J1 — Content quality evaluation.

Checks whether generated lessons contain the four structured fields added
in Phase A: key_concepts, worked_example, common_pitfalls, practice_prompts.

Usage:
    cd backend
    uv run python -m eval.j1_content_quality
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.course_agent import generate_course

RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

TEST_GOALS = [
    ("Learn Python basics for data science", "short_term", "Python"),
    ("Get conversational in Spanish in 2 weeks", "short_term", "Spanish"),
    ("Understand machine learning fundamentals", "short_term", "AI/ML"),
    ("Learn the basics of personal finance", "short_term", "Finance"),
    ("Understand modern web development", "short_term", "Technology"),
]

STRUCTURED_FIELDS = ["key_concepts", "worked_example", "common_pitfalls", "practice_prompts"]


def eval_lesson(lesson_data: dict) -> dict[str, bool]:
    """Check presence of the structured fields on the lesson object itself.

    These fields are siblings of `description` in the generated JSON, not
    nested inside it. The previous implementation json.loads()-ed the prose
    description, which throws on every real lesson and reported 0.0 coverage
    across the board.
    """
    return {field: bool(lesson_data.get(field)) for field in STRUCTURED_FIELDS}


def run() -> dict:
    results = []
    for goal, duration, category in TEST_GOALS:
        print(f"Generating: {goal[:50]}…")
        try:
            course_data = generate_course(goal=goal, duration=duration, category=category)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            results.append({"goal": goal, "error": str(exc)})
            continue

        lesson_results = []
        for module in course_data.get("modules", []):
            for lesson in module.get("lessons", []):
                fields = eval_lesson(lesson)
                lesson_results.append({"title": lesson.get("title"), "fields": fields})

        coverage = {}
        for field in STRUCTURED_FIELDS:
            count = sum(1 for lr in lesson_results if lr["fields"].get(field))
            coverage[field] = round(count / len(lesson_results), 3) if lesson_results else 0.0

        overall = round(sum(coverage.values()) / len(STRUCTURED_FIELDS), 3)
        results.append({
            "goal": goal,
            "category": category,
            "total_lessons": len(lesson_results),
            "field_coverage": coverage,
            "overall_score": overall,
        })
        print(f"  Coverage: {coverage}, overall={overall}")

    grand_total = sum(r.get("overall_score", 0) for r in results if "overall_score" in r)
    n = sum(1 for r in results if "overall_score" in r)
    summary = {
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "aggregate": {
            "mean_overall_score": round(grand_total / n, 3) if n else 0,
            "n_courses": n,
        },
    }

    out_path = RESULTS_DIR / f"j1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nResults written to {out_path}")
    return summary


if __name__ == "__main__":
    run()
