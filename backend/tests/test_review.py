"""Tests for GET /review/next and POST /review/grade.

Uses an in-memory SQLite database (StaticPool) — no Ollama, no real DB.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Card, Course, Lesson, Module, Objective, Question, Review  # noqa: F401


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


def _seed_card(db_session, due_offset_hours: int = -1) -> Card:
    """Insert the minimal Course→Module→Lesson→Question→Card chain.
    due_offset_hours < 0 → card already due; > 0 → card not yet due.
    """
    course = Course(
        goal="Learn Python",
        duration="short_term",
        category="Programming",
        title="Intro to Python",
        description="A short Python course.",
    )
    db_session.add(course)
    db_session.flush()

    module = Module(
        course_id=course.id,
        order_index=1,
        title="Basics",
        description="Python basics.",
    )
    db_session.add(module)
    db_session.flush()

    lesson = Lesson(
        module_id=module.id,
        order_index=1,
        title="Variables",
        description="Variable declaration.",
        duration_minutes=10,
    )
    db_session.add(lesson)
    db_session.flush()

    question = Question(
        lesson_id=lesson.id,
        order_index=1,
        text="What is a variable?",
        reference_answer="A variable is a named storage location in memory.",
        reference_embedding=json.dumps([0.0] * 384),
    )
    db_session.add(question)
    db_session.flush()

    due = datetime.now(timezone.utc) + timedelta(hours=due_offset_hours)
    card = Card(
        question_id=question.id,
        state=1,
        step=0,
        stability=None,
        difficulty=None,
        due=due.isoformat(),
        last_review=None,
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


# ---------------------------------------------------------------------------
# GET /review/next
# ---------------------------------------------------------------------------

def test_next_card_returns_204_when_no_cards_due(client):
    resp = client.get("/review/next")
    assert resp.status_code == 204


def test_next_card_returns_204_when_card_not_yet_due(client, db_session):
    _seed_card(db_session, due_offset_hours=24)
    resp = client.get("/review/next")
    assert resp.status_code == 204


def test_next_card_returns_200_with_due_card(client, db_session):
    card = _seed_card(db_session, due_offset_hours=-1)
    resp = client.get("/review/next")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == card.id
    assert data["question_id"] == card.question_id
    assert data["question_text"] == "What is a variable?"
    assert data["question_reference_answer"] == "A variable is a named storage location in memory."
    assert data["state"] == 1
    assert "due" in data


# ---------------------------------------------------------------------------
# POST /review/grade
# ---------------------------------------------------------------------------

def test_grade_updates_card_fields(client, db_session):
    card = _seed_card(db_session, due_offset_hours=-1)
    resp = client.post("/review/grade", json={"card_id": card.id, "rating": 3})
    assert resp.status_code == 200
    data = resp.json()
    assert data["card_id"] == card.id
    assert data["rating"] == 3
    assert data["stability"] is not None
    assert data["difficulty"] is not None
    assert data["due"] != card.due  # due must be updated


def test_grade_writes_review_row(client, db_session, test_engine):
    card = _seed_card(db_session, due_offset_hours=-1)
    client.post("/review/grade", json={"card_id": card.id, "rating": 3})

    # Open a fresh session to read the committed review row
    CheckSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    check_db = CheckSession()
    try:
        count = check_db.query(Review).filter(Review.card_id == card.id).count()
        assert count == 1
    finally:
        check_db.close()


def test_grade_multiple_times_accumulates_reviews(client, db_session, test_engine):
    card = _seed_card(db_session, due_offset_hours=-1)

    for rating in [3, 3, 1, 3]:
        resp = client.post("/review/grade", json={"card_id": card.id, "rating": rating})
        assert resp.status_code == 200

    CheckSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    check_db = CheckSession()
    try:
        count = check_db.query(Review).filter(Review.card_id == card.id).count()
        assert count == 4
    finally:
        check_db.close()


def test_grade_card_not_found_returns_404(client):
    resp = client.post("/review/grade", json={"card_id": str(uuid.uuid4()), "rating": 3})
    assert resp.status_code == 404


def test_grade_rating_too_low_returns_422(client, db_session):
    card = _seed_card(db_session, due_offset_hours=-1)
    resp = client.post("/review/grade", json={"card_id": card.id, "rating": 0})
    assert resp.status_code == 422


def test_grade_rating_too_high_returns_422(client, db_session):
    card = _seed_card(db_session, due_offset_hours=-1)
    resp = client.post("/review/grade", json={"card_id": card.id, "rating": 5})
    assert resp.status_code == 422


def test_grade_state_advances_on_good(client, db_session):
    """Two Good ratings should move card from Learning to Review."""
    card = _seed_card(db_session, due_offset_hours=-1)

    resp1 = client.post("/review/grade", json={"card_id": card.id, "rating": 3})
    assert resp1.status_code == 200

    resp2 = client.post("/review/grade", json={"card_id": card.id, "rating": 3})
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["state"] == 2  # State.Review
