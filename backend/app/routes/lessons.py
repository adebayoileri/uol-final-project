import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from fsrs import Card as FSRSCard
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Card as DBCard, Lesson, Module, Question
from app.schemas import QuestionResponse
from app.services.answer_evaluator import embed
from app.services.embeddings import index_question
from app.achievements.engine import evaluate_achievements
from app.services.events import LESSON_COMPLETED, record_event
from app.services.question_generator import generate_questions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.post(
    "/{lesson_id}/questions/generate",
    response_model=list[QuestionResponse],
    status_code=201,
)
def generate_lesson_questions(lesson_id: str, db: Session = Depends(get_db)):
    lesson = (
        db.query(Lesson)
        .options(
            selectinload(Lesson.objectives),
            selectinload(Lesson.module).selectinload(Module.course),
        )
        .filter(Lesson.id == lesson_id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")

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


@router.get("/{lesson_id}/questions", response_model=list[QuestionResponse])
def list_lesson_questions(lesson_id: str, db: Session = Depends(get_db)):
    if not db.get(Lesson, lesson_id):
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return (
        db.query(Question)
        .filter(Question.lesson_id == lesson_id)
        .order_by(Question.order_index)
        .all()
    )


@router.post("/{lesson_id}/complete", status_code=204)
def complete_lesson(lesson_id: str, db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    if lesson.completed_at is None:
        lesson.completed_at = datetime.now(timezone.utc)
        db.commit()
        record_event(db, LESSON_COMPLETED, {"lesson_id": lesson_id})
        evaluate_achievements(db)
    return Response(status_code=204)
