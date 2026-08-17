"""Pins the wiring between lessons.content_json and its downstream consumers.

These consumers were dead code until enrichment existed: their context blocks
were built correctly but always rendered empty because parse_lesson_body()
never saw JSON.
"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import Course, Lesson, Module, Objective
from app.services.lesson_chat import _build_context
from app.services.question_generator import _build_context_blocks
from tests.conftest import TEST_USER_ID

CONTENT = {
    "key_concepts": [
        {
            "name": "open()",
            "definition": "Returns a file object holding an OS handle.",
            "example": "f = open('data.txt')",
        }
    ],
    "worked_example": "Step 1: open the path.\nStep 2: read it.",
    "common_pitfalls": ["Never closing the handle."],
    "practice_prompts": ["Why close a file?"],
}

PROSE = "Content for open() and read()."


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine, autocommit=False, autoflush=False)()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)


def _seed_lesson(db_session, content_json=None) -> Lesson:
    course = Course(
        user_id=TEST_USER_ID,
        goal="Learn Python",
        duration="short_term",
        category="Programming",
        title="Python",
        description="A course.",
    )
    db_session.add(course)
    db_session.flush()
    module = Module(course_id=course.id, order_index=0, title="Basics", description="B.")
    db_session.add(module)
    db_session.flush()
    lesson = Lesson(
        module_id=module.id,
        order_index=0,
        title="Reading files",
        description=PROSE,
        duration_minutes=45,
        content_json=content_json,
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.add(Objective(lesson_id=lesson.id, order_index=0, description="Read a file."))
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# Question generation
# ---------------------------------------------------------------------------

def test_question_context_reads_content_json(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    blocks = _build_context_blocks(lesson)
    assert "open()" in blocks["key_concepts_block"]
    assert "Why close a file?" in blocks["practice_prompts_block"]


def test_question_context_keeps_description_as_prose(db_session):
    """The regression the separate column exists to prevent."""
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    blocks = _build_context_blocks(lesson)
    assert blocks["lesson_description"] == PROSE
    assert "{" not in blocks["lesson_description"]
    assert "key_concepts" not in blocks["lesson_description"]


def test_question_context_blocks_empty_when_unenriched(db_session):
    lesson = _seed_lesson(db_session, content_json=None)
    blocks = _build_context_blocks(lesson)
    assert blocks["key_concepts_block"] == ""
    assert blocks["practice_prompts_block"] == ""
    assert blocks["lesson_description"] == PROSE


def test_question_prompt_formats_with_enriched_blocks(db_session):
    from app.services.question_generator import _build_prompt

    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    prompt = _build_prompt(lesson)
    assert "open()" in prompt
    assert "Reading files" in prompt


# ---------------------------------------------------------------------------
# Tutor chat
# ---------------------------------------------------------------------------

def test_chat_context_reads_content_json():
    ctx = _build_context(PROSE, "Reading files", json.dumps(CONTENT))
    assert "open()" in ctx
    assert "Step 1: open the path." in ctx
    assert "Never closing the handle." in ctx
    assert "{" not in ctx


def test_chat_context_includes_prose_alongside_structured_content():
    ctx = _build_context(PROSE, "Reading files", json.dumps(CONTENT))
    assert PROSE in ctx
    assert "Key concepts:" in ctx


def test_chat_context_without_content_json_uses_prose():
    ctx = _build_context(PROSE, "Reading files", None)
    assert PROSE in ctx
    assert "Key concepts:" not in ctx


def test_chat_context_worked_example_not_truncated_at_400():
    long_example = "Step 1: " + ("x" * 900) + " Step 4: done."
    content = {**CONTENT, "worked_example": long_example}
    ctx = _build_context(PROSE, "Reading files", json.dumps(content))
    assert len(ctx) > 1000
