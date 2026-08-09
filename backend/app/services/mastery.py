"""Card and course mastery calculations.

Mastery formula: min(1.0, stability / 30)
— stability of 30 days represents ~90% retention at that interval,
  which we define as "full mastery". Below 30, mastery scales linearly.
  A stability of 0 (unseen/learning) → mastery 0.0.

See docs/decisions.md for the rationale.
"""

from sqlalchemy import text
from sqlalchemy.orm import Session

_FULL_MASTERY_STABILITY = 30.0


def card_mastery(stability: float | None) -> float:
    """Return 0.0–1.0 based on a card's FSRS stability value."""
    if stability is None or stability <= 0:
        return 0.0
    return min(1.0, stability / _FULL_MASTERY_STABILITY)


def course_mastery(course_id: str, db: Session) -> dict:
    """Return per-concept mastery and overall average for a course.

    Each 'concept' is represented by one card (keyed by first 60 chars of
    question text so the UI has a readable label).
    """
    rows = db.execute(
        text("""
            SELECT q.text as question_text, c.stability
            FROM cards c
            JOIN questions q ON q.id = c.question_id
            WHERE c.course_id = :course_id
            ORDER BY q.order_index
        """),
        {"course_id": course_id},
    ).fetchall()

    if not rows:
        return {"concepts": [], "overall": 0.0}

    concepts = [
        {
            "name": row.question_text[:60].strip(),
            "mastery": round(card_mastery(row.stability), 3),
        }
        for row in rows
    ]

    overall = round(sum(c["mastery"] for c in concepts) / len(concepts), 3)
    return {"concepts": concepts, "overall": overall}
