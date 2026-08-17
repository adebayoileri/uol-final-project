import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fsrs import Card as FSRSCard
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import current_user
from app.auth.ownership import get_owned_lesson
from app.database import get_db
from app.models import Card as DBCard, Lesson, Module, Question, User
from app.schemas import LessonEnrichResponse, QuestionResponse
from app.services.answer_evaluator import embed
from app.services.embeddings import index_question
from app.achievements.engine import evaluate_achievements
from app.services.events import LESSON_COMPLETED, record_event
from app.services.lesson_enricher import ensure_enriched, lesson_lock
from app.services.question_generator import generate_questions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post(
    "/{lesson_id}/questions/generate",
    response_model=list[QuestionResponse],
    status_code=201,
)
def generate_lesson_questions(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    lesson = get_owned_lesson(
        db,
        lesson_id,
        user.id,
        selectinload(Lesson.objectives),
        selectinload(Lesson.module).selectinload(Module.course),
    )

    try:
        questions_data = generate_questions(lesson)
    except RuntimeError as exc:
        logger.error("Question generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Question generation is temporarily unavailable. Please try again.",
        ) from exc

    questions = []
    for i, qdata in enumerate(questions_data):
        ref_emb = embed(qdata["reference_answer"])
        q = Question(
            lesson=lesson,
            order_index=i,
            text=qdata["question"],
            reference_answer=qdata["reference_answer"],
            reference_embedding=json.dumps(ref_emb),
            question_type=qdata.get("question_type", "open"),
            code_snippet=qdata.get("code_snippet"),
            course_id=lesson.module.course_id,
        )
        questions.append(q)

    db.add_all(questions)
    db.commit()
    for q in questions:
        db.refresh(q)
        fsrs_card = FSRSCard()
        db.add(DBCard(
            question_id=q.id,
            state=int(fsrs_card.state),
            step=fsrs_card.step,
            stability=fsrs_card.stability,
            difficulty=fsrs_card.difficulty,
            due=fsrs_card.due.isoformat(),
            last_review=fsrs_card.last_review.isoformat() if fsrs_card.last_review else None,
            course_id=lesson.module.course_id,
        ))
    db.commit()

    for q in questions:
        index_question(q, lesson, db)

    return [QuestionResponse.model_validate(q) for q in questions]


@router.post("/{lesson_id}/enrich", response_model=LessonEnrichResponse)
def enrich_lesson_content(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Generate (or return cached) deep content for a lesson.

    Deliberately a separate endpoint rather than part of GET lesson detail:
    this is a multi-second LLM call, and folding it into the detail request
    would turn an instant page into a long blank screen on every first open,
    mutate the database inside a GET, and make an enrichment failure break the
    lesson page itself.
    """
    lesson = get_owned_lesson(
        db,
        lesson_id,
        user.id,
        selectinload(Lesson.objectives),
        selectinload(Lesson.module).selectinload(Module.course),
    )

    if lesson.content_json:
        return LessonEnrichResponse(status="cached", content=lesson.content)

    with lesson_lock(lesson_id):
        # Mandatory: a request that blocked here loaded `lesson` before waiting,
        # so its Session still holds content_json = NULL. Without expiring it the
        # double-check below reads the stale value and generates anyway — the
        # lock would run and protect nothing.
        db.expire(lesson, ["content_json"])
        if lesson.content_json:
            return LessonEnrichResponse(status="cached", content=lesson.content)
        content = ensure_enriched(lesson, db)

    if content is None:
        raise HTTPException(
            status_code=503,
            detail="Deeper lesson content is temporarily unavailable. Please try again.",
        )
    return LessonEnrichResponse(status="generated", content=lesson.content)


@router.get("/{lesson_id}/questions", response_model=list[QuestionResponse])
def list_lesson_questions(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    get_owned_lesson(db, lesson_id, user.id)
    return (
        db.query(Question)
        .filter(Question.lesson_id == lesson_id)
        .order_by(Question.order_index)
        .all()
    )


@router.post("/{lesson_id}/complete", status_code=204)
def complete_lesson(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    lesson = get_owned_lesson(db, lesson_id, user.id)
    if lesson.completed_at is None:
        lesson.completed_at = datetime.now(timezone.utc)
        db.commit()
        record_event(db, LESSON_COMPLETED, {"lesson_id": lesson_id}, user_id=user.id)
        evaluate_achievements(db, user_id=user.id)
    return Response(status_code=204)
