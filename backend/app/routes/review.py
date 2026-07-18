import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fsrs import Card as FSRSCard, Rating, Scheduler
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Card, Review
from app.schemas import CardResponse, GradeRequest, GradeResponse

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


@router.get("/next", response_model=CardResponse)
def next_card(db: Session = Depends(get_db)):
    now_iso = datetime.now(timezone.utc).isoformat()
    card = (
        db.query(Card)
        .filter(Card.due <= now_iso)
        .order_by(Card.due)
        .first()
    )
    if card is None:
        return Response(status_code=204)
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
    )


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

    return GradeResponse(
        card_id=card.id,
        rating=body.rating,
        stability=card.stability,
        difficulty=card.difficulty,
        due=card.due,
        state=card.state,
    )
