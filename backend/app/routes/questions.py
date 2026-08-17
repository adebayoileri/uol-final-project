import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_question
from app.database import get_db
from app.models import Question, User
from app.schemas import AnswerRequest, AnswerResponse
from app.services.answer_evaluator import evaluate_answer, evaluate_code_answer
from app.achievements.engine import evaluate_achievements
from app.services.events import QUESTION_ANSWERED, record_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/questions", tags=["questions"])


@router.post("/{question_id}/answer", response_model=AnswerResponse)
def answer_question(
    question_id: str,
    body: AnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    question = get_owned_question(db, question_id, user.id)

    if question.question_type == "fill_blank":
        result = evaluate_code_answer(
            question_text=question.text,
            code_snippet=question.code_snippet or "",
            user_answer=body.answer,
            reference_answer=question.reference_answer,
        )
    else:
        ref_emb = json.loads(question.reference_embedding)
        result = evaluate_answer(
            question_text=question.text,
            user_answer=body.answer,
            reference_answer=question.reference_answer,
            reference_embedding=ref_emb,
        )
    record_event(
        db,
        QUESTION_ANSWERED,
        {"verdict": result.get("verdict"), "score": result.get("score")},
        user_id=user.id,
    )
    evaluate_achievements(db, user_id=user.id)
    return AnswerResponse(**result)
