import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fsrs import Card as FSRSCard, Rating, Scheduler
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, Course, Review
from app.schemas import (
    CardResponse,
    GradeRequest,
    GradeResponse,
    ReviewCourseGroup,
    ReviewQueueResponse,
)
from app.achievements.engine import evaluate_achievements
from app.services.events import REVIEW_GRADED, record_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/review", tags=["review"])

_scheduler = Scheduler()


def _to_fsrs_card(db_card: Card) -> FSRSCard:
    return FSRSCard.from_dict({
        "card_id": 0,
        "state": db_card.state,
        "step": db_card.step,
        "stability": db_card.stability,
        "difficulty": db_card.difficulty,
        "due": db_card.due,
        "last_review": db_card.last_review,
    })


def _parse_date(value: str | None, *, end_of_day: bool = False) -> datetime | None:
    """Accept YYYY-MM-DD or a full ISO timestamp. Returns None for junk."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if len(value) == 10 and end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _apply_card_filters(
    query,
    course_id: str | None,
    created_from: str | None,
    created_to: str | None,
    due_from: str | None,
    due_to: str | None,
):
    """Shared by /next, /queue and /courses.

    These three MUST filter identically — if the hub aggregates differently
    from the session, the counts shown before starting a session are a lie.

    Note `Card.due` is TEXT ISO-8601, so the due-range comparisons below are
    lexicographic. That is valid only because every value is written as
    normalised UTC ISO, which is the same assumption `Card.due <= now_iso`
    has always relied on. `Card.created_at` is a real DATETIME.
    """
    if course_id is not None:
        query = query.filter(Card.course_id == course_id)

    cf = _parse_date(created_from)
    if cf is not None:
        query = query.filter(Card.created_at >= cf)
    ct = _parse_date(created_to, end_of_day=True)
    if ct is not None:
        query = query.filter(Card.created_at <= ct)

    df = _parse_date(due_from)
    if df is not None:
        query = query.filter(Card.due >= df.isoformat())
    dt = _parse_date(due_to, end_of_day=True)
    if dt is not None:
        query = query.filter(Card.due <= dt.isoformat())

    return query


@router.get("/next", response_model=CardResponse)
def next_card(
    course_id: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    due_from: str | None = Query(default=None),
    due_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    now_iso = datetime.now(timezone.utc).isoformat()
    q = db.query(Card).filter(Card.due <= now_iso)
    q = _apply_card_filters(q, course_id, created_from, created_to, due_from, due_to)
    card = q.order_by(Card.due).first()
    if card is None:
        return Response(status_code=204)

    course_title = None
    try:
        course_title = card.question.lesson.module.course.title
    except AttributeError:
        pass

    return CardResponse(
        id=card.id,
        question_id=card.question_id,
        question_text=card.question.text,
        question_reference_answer=card.question.reference_answer,
        question_type=card.question.question_type,
        code_snippet=card.question.code_snippet,
        state=card.state,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        course_id=card.course_id,
        course_title=course_title,
    )


@router.get("/queue", response_model=ReviewQueueResponse)
def review_queue(
    course_id: str | None = Query(default=None),
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    due_from: str | None = Query(default=None),
    due_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat()
    end_of_week = (now + timedelta(days=7)).isoformat()

    base = _apply_card_filters(
        db.query(Card), course_id, created_from, created_to, due_from, due_to
    )

    return ReviewQueueResponse(
        total=base.count(),
        due_now=base.filter(Card.due <= now_iso).count(),
        due_today=base.filter(Card.due <= end_of_today).count(),
        due_this_week=base.filter(Card.due <= end_of_week).count(),
    )


@router.get("/courses", response_model=list[ReviewCourseGroup])
def review_courses(
    created_from: str | None = Query(default=None),
    created_to: str | None = Query(default=None),
    due_from: str | None = Query(default=None),
    due_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Per-course card counts, honouring the same filters as the session.

    Deliberately not derived from `GET /courses` — that endpoint's
    `progress_summary.due_now` takes no filter arguments, so it cannot answer
    "how many are due in this course *given these filters*", and the picker's
    numbers would disagree with the session the moment a filter is applied.
    """
    now_iso = datetime.now(timezone.utc).isoformat()

    rows = (
        _apply_card_filters(
            db.query(
                Card.course_id.label("course_id"),
                func.count(Card.id).label("total_cards"),
                func.sum(case((Card.due <= now_iso, 1), else_=0)).label("due_now"),
                func.min(Card.created_at).label("oldest_created_at"),
                func.max(Card.created_at).label("newest_created_at"),
            ).filter(Card.course_id.isnot(None)),  # a NULL bucket is not a course
            None,
            created_from,
            created_to,
            due_from,
            due_to,
        )
        .group_by(Card.course_id)
        .all()
    )

    courses = {c.id: c for c in db.query(Course).all()}

    out: list[ReviewCourseGroup] = []
    for row in rows:
        course = courses.get(row.course_id)
        if course is None:
            continue  # orphaned cards from a deleted course
        out.append(
            ReviewCourseGroup(
                course_id=row.course_id,
                title=course.title,
                category=course.category,
                total_cards=row.total_cards or 0,
                due_now=int(row.due_now or 0),
                oldest_created_at=row.oldest_created_at,
                newest_created_at=row.newest_created_at,
            )
        )

    out.sort(key=lambda g: (-g.due_now, g.title.lower()))
    return out


@router.get("/forecast")
def review_forecast(
    course_id: str | None = Query(default=None),
    days: int = Query(default=28, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Cards due per calendar day, for the review calendar.

    Anything already overdue is folded into today, which is where the user
    would actually see it. Days with no cards are returned with a count of 0 so
    the client never has to infer a gap.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    horizon = (now + timedelta(days=days)).isoformat()

    base = db.query(Card).filter(Card.due <= horizon)
    if course_id is not None:
        base = base.filter(Card.course_id == course_id)

    counts: dict[str, int] = {
        (today + timedelta(days=i)).isoformat(): 0 for i in range(days)
    }

    for (due,) in base.with_entities(Card.due).all():
        if not due:
            continue
        try:
            due_date = datetime.fromisoformat(due).date()
        except ValueError:
            continue
        key = max(due_date, today).isoformat()
        if key in counts:
            counts[key] += 1

    return [{"date": date, "count": count} for date, count in sorted(counts.items())]


@router.post("/grade", response_model=GradeResponse)
def grade_card(body: GradeRequest, db: Session = Depends(get_db)):
    card = db.get(Card, body.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found.")

    fsrs_card = _to_fsrs_card(card)
    updated, _review_log = _scheduler.review_card(fsrs_card, Rating(body.rating))

    card.state = int(updated.state)
    card.step = updated.step
    card.stability = updated.stability
    card.difficulty = updated.difficulty
    card.due = updated.due.isoformat()
    card.last_review = updated.last_review.isoformat() if updated.last_review else None

    db.add(Review(
        card_id=card.id,
        rating=body.rating,
        stability=updated.stability,
        difficulty=updated.difficulty,
    ))
    db.commit()
    db.refresh(card)
    record_event(db, REVIEW_GRADED, {"rating": body.rating, "card_id": body.card_id})
    evaluate_achievements(db)

    return GradeResponse(
        card_id=card.id,
        rating=body.rating,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        state=card.state,
    )
