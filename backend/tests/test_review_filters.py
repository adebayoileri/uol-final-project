"""Tests for review date filtering and the per-course hub aggregation.

The load-bearing property here is that /review/next, /review/queue and
/review/courses all filter identically — if the hub aggregates differently from
the session, the counts shown before starting a session are wrong.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Card, Course, Lesson, Module, Question


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
def db_session(test_engine):
    db = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)()
    try:
        yield db
    finally:
        db.close()


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


def _seed_course(db_session, title: str, category: str = "Programming") -> Course:
    course = Course(
        goal=f"Learn {title}",
        duration="short_term",
        category=category,
        title=title,
        description="A course.",
    )
    db_session.add(course)
    db_session.flush()
    module = Module(course_id=course.id, order_index=0, title="M", description="d")
    db_session.add(module)
    db_session.flush()
    lesson = Lesson(
        module_id=module.id, order_index=0, title="L", description="d", duration_minutes=10
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.commit()
    return course


def _seed_card(
    db_session,
    course: Course,
    *,
    due_offset_hours: int = -1,
    created_days_ago: int = 0,
) -> Card:
    lesson = (
        db_session.query(Lesson)
        .join(Module, Module.id == Lesson.module_id)
        .filter(Module.course_id == course.id)
        .first()
    )
    question = Question(
        lesson_id=lesson.id,
        order_index=0,
        text="What is it?",
        reference_answer="A thing.",
        reference_embedding=json.dumps([0.0] * 384),
        course_id=course.id,
    )
    db_session.add(question)
    db_session.flush()

    card = Card(
        question_id=question.id,
        state=1,
        step=0,
        due=(datetime.now(timezone.utc) + timedelta(hours=due_offset_hours)).isoformat(),
        course_id=course.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=created_days_ago),
    )
    db_session.add(card)
    db_session.commit()
    db_session.refresh(card)
    return card


def _day(offset_days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).date().isoformat()


# ---------------------------------------------------------------------------
# Created-date filter
# ---------------------------------------------------------------------------

def test_created_from_excludes_older_cards(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course, created_days_ago=30)
    _seed_card(db_session, course, created_days_ago=0)

    assert client.get("/review/queue").json()["due_now"] == 2
    assert client.get(f"/review/queue?created_from={_day(-7)}").json()["due_now"] == 1


def test_created_to_excludes_newer_cards(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course, created_days_ago=30)
    _seed_card(db_session, course, created_days_ago=0)

    assert client.get(f"/review/queue?created_to={_day(-7)}").json()["due_now"] == 1


def test_created_to_is_inclusive_of_the_whole_day(client, db_session):
    """A bare YYYY-MM-DD upper bound must include cards made later that day."""
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course, created_days_ago=0)
    assert client.get(f"/review/queue?created_to={_day(0)}").json()["due_now"] == 1


# ---------------------------------------------------------------------------
# Due-range filter
# ---------------------------------------------------------------------------

def test_due_range_narrows_the_pool(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course, due_offset_hours=-1)
    _seed_card(db_session, course, due_offset_hours=24 * 10)

    assert client.get("/review/queue").json()["total"] == 2
    assert client.get(f"/review/queue?due_to={_day(1)}").json()["total"] == 1
    assert client.get(f"/review/queue?due_from={_day(5)}").json()["total"] == 1


def test_filters_compose(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course, created_days_ago=30, due_offset_hours=-1)
    _seed_card(db_session, course, created_days_ago=0, due_offset_hours=-1)

    body = client.get(f"/review/queue?created_from={_day(-7)}&due_to={_day(1)}").json()
    assert body["due_now"] == 1


def test_out_of_range_filter_yields_204_and_zero(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course)

    assert client.get(f"/review/next?created_from={_day(5)}").status_code == 204
    assert client.get(f"/review/queue?created_from={_day(5)}").json()["due_now"] == 0


def test_malformed_date_is_ignored_rather_than_erroring(client, db_session):
    course = _seed_course(db_session, "A")
    _seed_card(db_session, course)
    resp = client.get("/review/queue?created_from=not-a-date")
    assert resp.status_code == 200
    assert resp.json()["due_now"] == 1


# ---------------------------------------------------------------------------
# Card provenance
# ---------------------------------------------------------------------------

def test_next_card_reports_its_course(client, db_session):
    course = _seed_course(db_session, "Chess")
    _seed_card(db_session, course)

    body = client.get("/review/next").json()
    assert body["course_id"] == course.id
    assert body["course_title"] == "Chess"


# ---------------------------------------------------------------------------
# Hub aggregation
# ---------------------------------------------------------------------------

def test_courses_groups_by_course(client, db_session):
    a = _seed_course(db_session, "Alpha")
    b = _seed_course(db_session, "Beta")
    _seed_card(db_session, a)
    _seed_card(db_session, a)
    _seed_card(db_session, b, due_offset_hours=24 * 30)

    rows = {r["title"]: r for r in client.get("/review/courses").json()}
    assert rows["Alpha"]["due_now"] == 2
    assert rows["Alpha"]["total_cards"] == 2
    assert rows["Beta"]["due_now"] == 0
    assert rows["Beta"]["total_cards"] == 1


def test_courses_is_ordered_by_due_count_desc(client, db_session):
    a = _seed_course(db_session, "Zeta")
    b = _seed_course(db_session, "Alpha")
    _seed_card(db_session, a)
    _seed_card(db_session, a)
    _seed_card(db_session, b)

    titles = [r["title"] for r in client.get("/review/courses").json()]
    assert titles[0] == "Zeta"


def test_courses_honours_the_same_filters_as_the_session(client, db_session):
    """The hub's number must equal what the session will actually serve."""
    course = _seed_course(db_session, "Alpha")
    _seed_card(db_session, course, created_days_ago=30)
    _seed_card(db_session, course, created_days_ago=0)

    qs = f"created_from={_day(-7)}"
    hub = client.get(f"/review/courses?{qs}").json()[0]
    session_total = client.get(f"/review/queue?course_id={course.id}&{qs}").json()["due_now"]

    assert hub["due_now"] == session_total == 1


def test_courses_excludes_cards_with_no_course(client, db_session):
    course = _seed_course(db_session, "Alpha")
    card = _seed_card(db_session, course)
    card.course_id = None
    db_session.commit()

    assert client.get("/review/courses").json() == []


def test_courses_reports_created_bounds(client, db_session):
    course = _seed_course(db_session, "Alpha")
    _seed_card(db_session, course, created_days_ago=10)
    _seed_card(db_session, course, created_days_ago=0)

    row = client.get("/review/courses").json()[0]
    assert row["oldest_created_at"] is not None
    assert row["newest_created_at"] >= row["oldest_created_at"]


def test_courses_empty_when_no_cards(client):
    assert client.get("/review/courses").json() == []
