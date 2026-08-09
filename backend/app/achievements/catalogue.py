"""Achievement catalogue — definitions and check functions."""

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.events import LESSON_COMPLETED, QUESTION_ANSWERED
from app.services.streaks import current_streak


@dataclass
class Achievement:
    id: str
    title: str
    description: str
    icon: str
    check_fn: Callable[[Session], bool]


def _check_course_champion(db: Session) -> bool:
    """At least one course where all lessons are completed."""
    row = db.execute(text("""
        SELECT c.id
        FROM courses c
        WHERE (
            SELECT COUNT(*) FROM modules m
            JOIN lessons l ON l.module_id = m.id
            WHERE m.course_id = c.id
        ) > 0
        AND (
            SELECT COUNT(*) FROM modules m
            JOIN lessons l ON l.module_id = m.id
            WHERE m.course_id = c.id AND l.completed_at IS NULL
        ) = 0
        LIMIT 1
    """)).fetchone()
    return row is not None


def _check_consistent_learner(db: Session) -> bool:
    return current_streak(db) >= 5


def _check_memory_master(db: Session) -> bool:
    """At least one course where ≥80% of cards have stability > 10."""
    row = db.execute(text("""
        SELECT course_id,
               COUNT(*) as total,
               SUM(CASE WHEN stability > 10 THEN 1 ELSE 0 END) as stable
        FROM cards
        WHERE course_id IS NOT NULL
        GROUP BY course_id
        HAVING total > 0 AND CAST(stable AS FLOAT) / total >= 0.8
        LIMIT 1
    """)).fetchone()
    return row is not None


def _check_question_master(db: Session) -> bool:
    """50 QUESTION_ANSWERED events with verdict=correct in metadata."""
    row = db.execute(
        text("""
            SELECT COUNT(*) as cnt
            FROM user_events
            WHERE event_type = :et AND json_extract(metadata, '$.verdict') = 'correct'
        """),
        {"et": QUESTION_ANSWERED},
    ).fetchone()
    return (row.cnt if row else 0) >= 50


CATALOGUE: list[Achievement] = [
    Achievement(
        id="course_champion",
        title="Course Champion",
        description="Complete all lessons in any course.",
        icon="🏆",
        check_fn=_check_course_champion,
    ),
    Achievement(
        id="consistent_learner",
        title="Consistent Learner",
        description="Study for 5 consecutive days.",
        icon="🔥",
        check_fn=_check_consistent_learner,
    ),
    Achievement(
        id="memory_master",
        title="Memory Master",
        description="Reach high stability (>10 days) on 80% of a course's cards.",
        icon="🧠",
        check_fn=_check_memory_master,
    ),
    Achievement(
        id="question_master",
        title="Question Master",
        description="Answer 50 questions correctly.",
        icon="⭐",
        check_fn=_check_question_master,
    ),
]
