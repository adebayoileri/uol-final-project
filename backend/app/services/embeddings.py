"""Semantic search: index lesson/question content into content_embeddings, search via cosine similarity."""

import logging
import time

import numpy as np
from sqlalchemy.orm import Session

from app.models import ContentEmbedding
from app.services.answer_evaluator import embed

logger = logging.getLogger(__name__)


def _to_blob(text: str) -> bytes:
    return np.array(embed(text), dtype=np.float32).tobytes()


def index_lesson(lesson, db: Session) -> None:
    text = f"{lesson.title}: {lesson.description}"
    blob = _to_blob(text)
    course_id = lesson.module.course_id

    row = (
        db.query(ContentEmbedding)
        .filter(
            ContentEmbedding.content_type == "lesson",
            ContentEmbedding.content_id == lesson.id,
        )
        .first()
    )
    if row:
        row.vector = blob
        row.content_text = text
    else:
        db.add(
            ContentEmbedding(
                content_type="lesson",
                content_id=lesson.id,
                content_text=text,
                course_id=course_id,
                lesson_id=None,
                vector=blob,
            )
        )
    db.commit()


def index_question(question, lesson, db: Session) -> None:
    blob = _to_blob(question.text)
    course_id = lesson.module.course_id

    row = (
        db.query(ContentEmbedding)
        .filter(
            ContentEmbedding.content_type == "question",
            ContentEmbedding.content_id == question.id,
        )
        .first()
    )
    if row:
        row.vector = blob
        row.content_text = question.text
    else:
        db.add(
            ContentEmbedding(
                content_type="question",
                content_id=question.id,
                content_text=question.text,
                course_id=course_id,
                lesson_id=lesson.id,
                vector=blob,
            )
        )
    db.commit()


def search(query: str, k: int, db: Session, course_id: str | None = None) -> list[dict]:
    t0 = time.perf_counter()

    q_vec = np.array(embed(query), dtype=np.float32)
    q_norm = np.linalg.norm(q_vec)
    q_vec = q_vec / (q_norm + 1e-10)

    rows_q = db.query(ContentEmbedding)
    if course_id:
        rows_q = rows_q.filter(ContentEmbedding.course_id == course_id)
    rows = rows_q.all()

    if not rows:
        return []

    vecs = np.stack([np.frombuffer(r.vector, dtype=np.float32) for r in rows])  # (N, 384)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    similarities = (vecs / (norms + 1e-10)) @ q_vec  # (N,)

    top_indices = np.argsort(similarities)[::-1][:k]
    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info("search over %d items in %.1f ms", len(rows), elapsed_ms)

    return [
        {
            "content_type": rows[i].content_type,
            "content_id": rows[i].content_id,
            "content_text": rows[i].content_text,
            "course_id": rows[i].course_id,
            "lesson_id": rows[i].lesson_id,
            "score": float(similarities[i]),
        }
        for i in top_indices
    ]
