"""Tests for events.record_event and streaks.current_streak."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services.events import (
    LESSON_COMPLETED,
    REVIEW_GRADED,
    record_event,
)
from app.services.streaks import current_streak, total_study_time_minutes


@pytest.fixture()
def db(tmp_path):
    """In-memory SQLite session with event/session tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE user_events (
                id TEXT PRIMARY KEY,
                event_type TEXT NOT NULL,
                occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT NOT NULL DEFAULT '{}'
            )
        """))
        conn.execute(text("""
            CREATE TABLE study_sessions (
                id TEXT PRIMARY KEY,
                started_at DATETIME NOT NULL,
                last_activity_at DATETIME NOT NULL,
                event_count INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.commit()

    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _insert_event(db, event_type: str, occurred_at: datetime):
    """Directly insert an event with a specific timestamp (bypasses record_event timestamp)."""
    import uuid, json
    db.execute(
        text("""
            INSERT INTO user_events (id, event_type, occurred_at, metadata)
            VALUES (:id, :type, :at, :meta)
        """),
        {"id": str(uuid.uuid4()), "type": event_type, "at": occurred_at, "meta": json.dumps({})},
    )
    db.commit()


def test_no_events_streak_zero(db):
    assert current_streak(db) == 0


def test_single_day_streak(db):
    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0)
    _insert_event(db, LESSON_COMPLETED, today)
    assert current_streak(db) == 1


def test_three_day_streak(db):
    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0)
    for delta in [0, 1, 2]:
        _insert_event(db, LESSON_COMPLETED, today - timedelta(days=delta))
    assert current_streak(db) == 3


def test_gap_breaks_streak(db):
    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0)
    # Events on today and 3 days ago — gap of 2 days in between
    _insert_event(db, LESSON_COMPLETED, today)
    _insert_event(db, LESSON_COMPLETED, today - timedelta(days=3))
    # Streak should be 1 (today only)
    assert current_streak(db) == 1


def test_review_graded_counts_for_streak(db):
    today = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0)
    _insert_event(db, REVIEW_GRADED, today)
    _insert_event(db, REVIEW_GRADED, today - timedelta(days=1))
    assert current_streak(db) == 2


def test_record_event_creates_study_session(db):
    record_event(db, LESSON_COMPLETED, {"lesson_id": "abc"})
    rows = db.execute(text("SELECT * FROM study_sessions")).fetchall()
    assert len(rows) == 1
    assert rows[0].event_count == 1


def test_record_event_extends_session_within_gap(db):
    record_event(db, LESSON_COMPLETED, {})
    record_event(db, REVIEW_GRADED, {})
    rows = db.execute(text("SELECT * FROM study_sessions")).fetchall()
    assert len(rows) == 1
    assert rows[0].event_count == 2
