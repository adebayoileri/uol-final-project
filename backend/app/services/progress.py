from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Card, Lesson, Module


def course_progress(course_id: str, db: Session) -> dict:
    now_iso = datetime.now(timezone.utc).isoformat()

    total_lessons = (
        db.query(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .filter(Module.course_id == course_id)
        .count()
    )
    completed_lessons = (
        db.query(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .filter(Module.course_id == course_id, Lesson.completed_at.isnot(None))
        .count()
    )
    total_cards = db.query(Card).filter(Card.course_id == course_id).count()
    due_now = (
        db.query(Card)
        .filter(Card.course_id == course_id, Card.due <= now_iso)
        .count()
    )
    return {
        "total_lessons": total_lessons,
        "completed_lessons": completed_lessons,
        "total_cards": total_cards,
        "due_now": due_now,
    }
