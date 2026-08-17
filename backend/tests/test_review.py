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
from tests.conftest import TEST_USER_ID


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


def _seed_card(
    db_session,
    due_offset_hours: int = -1,
    course_id: str | None = None,
    due_at: datetime | None = None,
) -> Card:
    """Insert the minimal Course→Module→Lesson→Question→Card chain.
    due_offset_hours < 0 → card already due; > 0 → card not yet due.
    due_at overrides the offset entirely, for tests that must not depend on
    the time of day at which the suite happens to run.
    course_id overrides the generated course's id on the card for scope testing.
    """
    course = Course(
        user_id=TEST_USER_ID,
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

    due = due_at or (datetime.now(timezone.utc) + timedelta(hours=due_offset_hours))
    card = Card(
        question_id=question.id,
        state=1,
        step=0,
        stability=None,
        difficulty=None,
        due=due.isoformat(),
        last_review=None,
        course_id=course_id,
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


# ---------------------------------------------------------------------------
# R2 — course_id scoping tests
# ---------------------------------------------------------------------------

def test_next_card_scoped_to_correct_course(client, db_session):
    """course_id param returns the matching course's card, ignoring other courses."""
    card_a = _seed_card(db_session, course_id="cid-a", due_offset_hours=-1)
    _seed_card(db_session, course_id="cid-b", due_offset_hours=-1)
    resp = client.get("/review/next?course_id=cid-a")
    assert resp.status_code == 200
    assert resp.json()["id"] == card_a.id


def test_next_out_of_scope_card_returns_204(client, db_session):
    """course_id filter excludes cards from other courses even when they are due."""
    _seed_card(db_session, course_id="cid-a", due_offset_hours=-1)
    resp = client.get("/review/next?course_id=cid-b")
    assert resp.status_code == 204


def test_next_future_card_in_scope_returns_204(client, db_session):
    """A not-yet-due card in the matching course returns 204."""
    _seed_card(db_session, course_id="cid-a", due_offset_hours=+24)
    resp = client.get("/review/next?course_id=cid-a")
    assert resp.status_code == 204


def test_queue_counts_scoped_and_mixed(client, db_session):
    """Queue endpoint returns correct counts for mixed due dates, excluding other courses."""
    cid = "cid-queue"
    now = datetime.now(timezone.utc)
    # Anchored to the end of the current UTC day rather than "now + 3h", which
    # silently falls into tomorrow whenever the suite runs after 21:00 UTC.
    later_today = now.replace(hour=23, minute=0, second=0, microsecond=0)
    if later_today <= now:
        later_today = now + timedelta(minutes=1)

    _seed_card(db_session, course_id=cid, due_offset_hours=-1)    # overdue → due_now + today + week
    _seed_card(db_session, course_id=cid, due_at=later_today)     # later today → today + week
    _seed_card(db_session, course_id=cid, due_offset_hours=+50)   # due in 50h (~2d) → week only
    _seed_card(db_session, course_id=cid, due_offset_hours=+200)  # due in 200h (~8d) → none
    _seed_card(db_session, course_id="other-cid", due_offset_hours=-1)  # excluded by scope

    resp = client.get(f"/review/queue?course_id={cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 4
    assert data["due_now"] == 1
    assert data["due_today"] == 2   # the overdue card and the one due later today
    assert data["due_this_week"] == 3  # -1h, +3h, +50h all within 7 days


# ---------------------------------------------------------------------------
# GET /review/forecast
# ---------------------------------------------------------------------------

def test_forecast_returns_one_row_per_day(client):
    resp = client.get("/review/forecast?days=7")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 7
    assert all(set(row) == {"date", "count"} for row in body)


def test_forecast_dates_are_consecutive_and_sorted(client):
    body = client.get("/review/forecast?days=5").json()
    dates = [datetime.fromisoformat(row["date"]).date() for row in body]
    assert dates == sorted(dates)
    assert dates[0] == datetime.now(timezone.utc).date()
    for earlier, later in zip(dates, dates[1:]):
        assert (later - earlier).days == 1


def test_forecast_is_all_zero_with_no_cards(client):
    body = client.get("/review/forecast?days=14").json()
    assert sum(row["count"] for row in body) == 0


def test_forecast_counts_a_future_card_on_its_due_day(client, db_session):
    _seed_card(db_session, due_offset_hours=48)
    body = client.get("/review/forecast?days=14").json()
    assert sum(row["count"] for row in body) == 1
    hit = next(row for row in body if row["count"] == 1)
    expected = (datetime.now(timezone.utc) + timedelta(hours=48)).date().isoformat()
    assert hit["date"] == expected


def test_forecast_folds_overdue_cards_into_today(client, db_session):
    _seed_card(db_session, due_offset_hours=-72)
    body = client.get("/review/forecast?days=14").json()
    today = datetime.now(timezone.utc).date().isoformat()
    assert body[0]["date"] == today
    assert body[0]["count"] == 1


def test_forecast_excludes_cards_beyond_the_horizon(client, db_session):
    _seed_card(db_session, due_offset_hours=24 * 40)
    body = client.get("/review/forecast?days=7").json()
    assert sum(row["count"] for row in body) == 0


def test_forecast_scoped_to_course(client, db_session):
    _seed_card(db_session, due_offset_hours=24, course_id="cid-a")
    _seed_card(db_session, due_offset_hours=24, course_id="cid-b")
    body = client.get("/review/forecast?course_id=cid-a&days=14").json()
    assert sum(row["count"] for row in body) == 1


def test_forecast_rejects_out_of_range_days(client):
    assert client.get("/review/forecast?days=0").status_code == 422
    assert client.get("/review/forecast?days=91").status_code == 422
