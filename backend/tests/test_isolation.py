"""Cross-user isolation.

Two really-registered accounts with real session cookies against one database.
Each user gets their own TestClient because each keeps its own cookie jar.

The autouse auth bypass from conftest is dropped here — with it, every request
would be pre-authenticated as the same user and these tests would prove nothing.
"""

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.deps import current_user
from app.database import Base, get_db
from app.main import app
from app.models import Card, Course, Lesson, Module, Question

A_CREDS = {"email": "alice@example.com", "password": "alice-password-1"}
B_CREDS = {"email": "bob@example.com", "password": "bob-password-11"}

# Distinctive enough that a search hit could only come from A's content.
SECRET_TOPIC = "zarquon flux capacitor calibration"


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # Raw-SQL tables live in _run_migrations(), not Base.metadata.
    with engine.connect() as conn:
        for ddl in (
            """CREATE TABLE IF NOT EXISTS user_events (
                   id TEXT PRIMARY KEY, user_id TEXT, event_type TEXT NOT NULL,
                   occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   metadata TEXT NOT NULL DEFAULT '{}')""",
            """CREATE TABLE IF NOT EXISTS study_sessions (
                   id TEXT PRIMARY KEY, user_id TEXT, started_at DATETIME NOT NULL,
                   last_activity_at DATETIME NOT NULL, event_count INTEGER NOT NULL DEFAULT 0)""",
            """CREATE TABLE IF NOT EXISTS user_achievements (
                   id TEXT PRIMARY KEY, user_id TEXT NOT NULL, achievement_id TEXT NOT NULL,
                   unlocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                   UNIQUE (user_id, achievement_id))""",
            """CREATE TABLE IF NOT EXISTS lesson_chat_messages (
                   id TEXT PRIMARY KEY, lesson_id TEXT NOT NULL, role TEXT NOT NULL,
                   content TEXT NOT NULL,
                   created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
        ):
            conn.execute(sql_text(ddl))
        conn.commit()
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
def clients(test_engine, bypass_auth):
    """Two signed-in users sharing one database."""
    app.dependency_overrides.pop(current_user, None)

    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as alice, TestClient(app) as bob:
        assert alice.post("/auth/register", json=A_CREDS).status_code == 201
        assert bob.post("/auth/register", json=B_CREDS).status_code == 201
        yield alice, bob

    app.dependency_overrides.clear()


@pytest.fixture()
def alice_content(clients, db_session):
    """A full course tree owned by Alice, plus one due card."""
    alice, _ = clients
    user_id = db_session.execute(
        sql_text("SELECT id FROM users WHERE email = :e"), {"e": A_CREDS["email"]}
    ).scalar_one()

    course = Course(
        user_id=user_id,
        goal=f"Learn {SECRET_TOPIC}",
        duration="short_term",
        category="Engineering",
        title=f"Course on {SECRET_TOPIC}",
        description="Alice's private course.",
    )
    db_session.add(course)
    db_session.flush()

    module = Module(course_id=course.id, order_index=0, title="M", description="d")
    db_session.add(module)
    db_session.flush()

    lesson = Lesson(
        module_id=module.id,
        order_index=0,
        title=f"Lesson about {SECRET_TOPIC}",
        description="Alice's private lesson prose.",
        duration_minutes=30,
    )
    db_session.add(lesson)
    db_session.flush()

    question = Question(
        lesson_id=lesson.id,
        order_index=0,
        text="What is the flux calibration constant?",
        reference_answer="Alice's private reference answer.",
        reference_embedding=json.dumps([0.0] * 384),
        course_id=course.id,
    )
    db_session.add(question)
    db_session.flush()

    card = Card(
        question_id=question.id,
        state=1,
        step=0,
        due=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        course_id=course.id,
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(card)
    db_session.commit()

    return {
        "user_id": user_id,
        "course_id": course.id,
        "lesson_id": lesson.id,
        "question_id": question.id,
        "card_id": card.id,
    }


# ---------------------------------------------------------------------------
# The matrix: adding a route means adding a line here.
# ---------------------------------------------------------------------------

CROSS_USER_ROUTES = [
    ("GET", "/courses/{course_id}"),
    ("GET", "/courses/{course_id}/mastery"),
    ("GET", "/courses/{course_id}/timeline"),
    ("GET", "/courses/{course_id}/insights"),
    ("GET", "/courses/{course_id}/certificate"),
    ("GET", "/courses/{course_id}/lessons/{lesson_id}"),
    ("GET", "/courses/{course_id}/drills"),
    ("GET", "/courses/{course_id}/drills/mcq"),
    ("POST", "/courses/{course_id}/drills/mcq/complete"),
    ("GET", "/lessons/{lesson_id}/questions"),
    ("POST", "/lessons/{lesson_id}/complete"),
    ("POST", "/lessons/{lesson_id}/enrich"),
    ("POST", "/lessons/{lesson_id}/narration"),
    ("GET", "/lessons/{lesson_id}/chat/history"),
]


@pytest.mark.parametrize("method,template", CROSS_USER_ROUTES)
def test_bob_cannot_reach_alices_resources(clients, alice_content, method, template):
    _, bob = clients
    path = template.format(**alice_content)
    resp = bob.request(method, path)
    assert resp.status_code == 404, f"{method} {path} returned {resp.status_code}"


def test_bob_cannot_answer_alices_question(clients, alice_content):
    _, bob = clients
    resp = bob.post(
        f"/questions/{alice_content['question_id']}/answer", json={"answer": "guess"}
    )
    assert resp.status_code == 404


def test_bob_cannot_chat_on_alices_lesson(clients, alice_content):
    _, bob = clients
    resp = bob.post(
        f"/lessons/{alice_content['lesson_id']}/chat",
        json={"message": "hello", "history": []},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Shape-different cases — these are the ones that catch real bugs
# ---------------------------------------------------------------------------

def test_course_list_is_empty_for_the_other_user(clients, alice_content):
    """An empty list, not a 404 — that IS correct scoping."""
    alice, bob = clients
    assert len(alice.get("/courses").json()) == 1
    assert bob.get("/courses").json() == []


def test_review_next_serves_nothing_to_the_other_user(clients, alice_content):
    """Alice has a due card. Bob must get 204, not her question and its answer."""
    alice, bob = clients
    assert alice.get("/review/next").status_code == 200
    assert bob.get("/review/next").status_code == 204


def test_review_queue_counts_are_per_user(clients, alice_content):
    alice, bob = clients
    assert alice.get("/review/queue").json()["due_now"] == 1
    assert bob.get("/review/queue").json()["due_now"] == 0


def test_review_courses_hub_is_per_user(clients, alice_content):
    alice, bob = clients
    assert len(alice.get("/review/courses").json()) == 1
    assert bob.get("/review/courses").json() == []


def test_review_forecast_is_per_user(clients, alice_content):
    alice, bob = clients
    assert sum(d["count"] for d in alice.get("/review/forecast").json()) == 1
    assert sum(d["count"] for d in bob.get("/review/forecast").json()) == 0


def test_search_does_not_leak_content_across_users(clients, alice_content, db_session):
    """The bulk leak: search needed no id guessing at all."""
    from app.services.embeddings import index_lesson

    lesson = db_session.get(Lesson, alice_content["lesson_id"])
    index_lesson(lesson, db_session)

    alice, bob = clients
    assert alice.get(f"/search?q={SECRET_TOPIC}").json(), "Alice should find her own content"
    assert bob.get(f"/search?q={SECRET_TOPIC}").json() == []


def test_bob_cannot_grade_alices_card(clients, alice_content, db_session):
    _, bob = clients
    before = db_session.get(Card, alice_content["card_id"]).due

    resp = bob.post("/review/grade", json={"card_id": alice_content["card_id"], "rating": 3})
    assert resp.status_code == 404

    # A 404 returned AFTER a write is not isolation.
    db_session.expire_all()
    assert db_session.get(Card, alice_content["card_id"]).due == before


def test_a_rejected_completion_does_not_mutate(clients, alice_content, db_session):
    """The assertion that actually proves isolation rather than just concealment."""
    _, bob = clients
    assert bob.post(f"/lessons/{alice_content['lesson_id']}/complete").status_code == 404

    db_session.expire_all()
    assert db_session.get(Lesson, alice_content["lesson_id"]).completed_at is None


def test_achievements_are_per_user(clients, alice_content, db_session):
    """The old schema had achievement_id globally UNIQUE, so the first user to
    unlock one blocked everybody."""
    alice, bob = clients
    for email, achievement in ((A_CREDS["email"], "course_champion"),):
        uid = db_session.execute(
            sql_text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
        db_session.execute(
            sql_text(
                "INSERT INTO user_achievements (id, user_id, achievement_id) "
                "VALUES ('x1', :uid, :a)"
            ),
            {"uid": uid, "a": achievement},
        )
    db_session.commit()

    alice_unlocked = {a["id"] for a in alice.get("/achievements").json() if a["unlocked"]}
    bob_unlocked = {a["id"] for a in bob.get("/achievements").json() if a["unlocked"]}

    assert "course_champion" in alice_unlocked
    assert bob_unlocked == set()


def test_a_second_user_can_unlock_the_same_achievement(clients, db_session):
    """Directly pins the composite UNIQUE."""
    uids = [
        db_session.execute(
            sql_text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
        for email in (A_CREDS["email"], B_CREDS["email"])
    ]
    for i, uid in enumerate(uids):
        db_session.execute(
            sql_text(
                "INSERT INTO user_achievements (id, user_id, achievement_id) "
                "VALUES (:id, :uid, 'question_master')"
            ),
            {"id": f"row{i}", "uid": uid},
        )
    db_session.commit()

    count = db_session.execute(
        sql_text("SELECT COUNT(*) FROM user_achievements WHERE achievement_id = 'question_master'")
    ).scalar_one()
    assert count == 2


def test_study_sessions_do_not_merge_across_users(clients, db_session):
    """Two users active seconds apart previously shared one session row."""
    from app.services.events import LESSON_COMPLETED, record_event

    uids = [
        db_session.execute(
            sql_text("SELECT id FROM users WHERE email = :e"), {"e": email}
        ).scalar_one()
        for email in (A_CREDS["email"], B_CREDS["email"])
    ]
    for uid in uids:
        record_event(db_session, LESSON_COMPLETED, {}, user_id=uid)

    rows = db_session.execute(sql_text("SELECT user_id FROM study_sessions")).fetchall()
    assert len(rows) == 2
    assert {r.user_id for r in rows} == set(uids)


def test_unauthenticated_requests_are_rejected(test_engine):
    """No cookie at all: the gate itself, not just the scoping."""
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides.pop(current_user, None)
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as anon:
        for path in ("/courses", "/review/next", "/review/queue", "/achievements", "/search?q=x"):
            assert anon.get(path).status_code == 401, path
    app.dependency_overrides.clear()
