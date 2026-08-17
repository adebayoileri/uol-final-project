"""Ownership checks.

`Course` is the root of the content tree, so every other entity is owned by
whoever owns its course. These walk that chain.

They raise **404, not 403**, for two reasons: a 403 confirms the id exists, so a
leaked URL or screenshot becomes an oracle; and every one of these routes
already raises 404 with the same message for an unknown id, so reusing it means
the frontend, the error components and the existing tests need no new branch.

Plain functions rather than FastAPI dependencies: `/review/grade` takes its id
from the request *body*, the eager-load options differ per route, and the chat
route needs a check inside a streaming generator. One mechanism used uniformly
beats two used cleverly.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Card, Course, Lesson, Module, Question


def owned_course_ids(user_id: str):
    """Scalar subquery of this user's course ids, for `.in_()` filters.

    Kept as a subquery rather than a materialised list so scoping stays a
    single SQL statement.
    """
    return select(Course.id).where(Course.user_id == user_id).scalar_subquery()


def get_owned_course(db: Session, course_id: str, user_id: str, *options) -> Course:
    query = db.query(Course)
    if options:
        query = query.options(*options)
    course = query.filter(Course.id == course_id, Course.user_id == user_id).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    return course


def get_owned_lesson(db: Session, lesson_id: str, user_id: str, *options) -> Lesson:
    query = db.query(Lesson)
    if options:
        query = query.options(*options)
    lesson = (
        query.join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .filter(Lesson.id == lesson_id, Course.user_id == user_id)
        .first()
    )
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return lesson


def get_owned_question(db: Session, question_id: str, user_id: str, *options) -> Question:
    query = db.query(Question)
    if options:
        query = query.options(*options)
    question = (
        query.join(Lesson, Lesson.id == Question.lesson_id)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .filter(Question.id == question_id, Course.user_id == user_id)
        .first()
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return question


def get_owned_card(db: Session, card_id: str, user_id: str, *options) -> Card:
    """Walks Card → Question → Lesson → Module → Course.

    Deliberately not via `cards.course_id`: that column is a nullable
    denormalisation, so trusting it would fail open on a NULL.
    """
    query = db.query(Card)
    if options:
        query = query.options(*options)
    card = (
        query.join(Question, Question.id == Card.question_id)
        .join(Lesson, Lesson.id == Question.lesson_id)
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .filter(Card.id == card_id, Course.user_id == user_id)
        .first()
    )
    if card is None:
        raise HTTPException(status_code=404, detail="Card not found.")
    return card
