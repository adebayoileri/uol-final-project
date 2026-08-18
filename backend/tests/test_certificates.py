"""Tests for certificate generation.

Written after the endpoint was found to have never worked once. The renderer
raised on its first line for a missing system library, and the only test
touching the URL asserted a cross-user 404 — which short-circuits at the
ownership check, so the generator was never called and the suite stayed green
through the entire life of the feature.

The load-bearing assertion here is therefore the least clever one: that the
response actually begins with %PDF.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module
from app.services.certificates import render_certificate_pdf
from tests.conftest import TEST_USER_ID


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS certificate_cache (
                course_id TEXT PRIMARY KEY,
                mastery_snapshot REAL NOT NULL,
                pdf_path TEXT NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                recipient TEXT
            )
        """))
        conn.commit()
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(test_engine):
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(test_engine, tmp_path, monkeypatch):
    # Certificates are cached to disk by course id. Without isolating the
    # directory, one test's PDF satisfies the next test's cache — the same
    # defect already found and fixed in the drill-audio tests.
    monkeypatch.setattr("app.services.certificates._CERT_DIR", tmp_path)

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


def _seed_course(db_session, *, lessons: int = 2, complete: bool = True) -> Course:
    course = Course(
        user_id=TEST_USER_ID,
        goal="Learn chess",
        duration="short_term",
        category="Games",
        title="Learning Chess Fundamentals",
        description="A short course.",
    )
    db_session.add(course)
    db_session.flush()

    module = Module(course_id=course.id, order_index=0, title="Basics", description="B.")
    db_session.add(module)
    db_session.flush()

    for i in range(lessons):
        db_session.add(Lesson(
            module_id=module.id,
            order_index=i,
            title=f"Lesson {i}",
            description="Body.",
            duration_minutes=30,
            completed_at=datetime.now(timezone.utc) if complete else None,
        ))
    db_session.commit()
    db_session.refresh(course)
    return course


# ---------------------------------------------------------------------------
# The renderer, in isolation
# ---------------------------------------------------------------------------

def test_renderer_produces_a_real_pdf():
    pdf = render_certificate_pdf("Learning Chess Fundamentals", 42.7, "Ada Lovelace")
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 800


def test_renderer_survives_characters_a_core_font_cannot_encode():
    """Titles are model-generated, so smart quotes and dashes are routine."""
    pdf = render_certificate_pdf(
        "History of AI — “Machine Learning”, 1956–1970s", 0.0, "José Ñuñez"
    )
    assert pdf[:5] == b"%PDF-"


def test_renderer_does_not_overflow_on_a_very_long_title():
    """Shrink-to-fit keeps the date on the page rather than pushing it off."""
    pdf = render_certificate_pdf("Deep " * 60, 100.0, "The Learner")
    assert pdf[:5] == b"%PDF-"


def test_renderer_accepts_zero_mastery():
    assert render_certificate_pdf("A Course", 0.0, "The Learner")[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

def test_certificate_downloads_as_a_pdf(client, db_session):
    """The assertion whose absence let a permanently broken feature ship."""
    course = _seed_course(db_session)
    res = client.get(f"/courses/{course.id}/certificate")

    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:5] == b"%PDF-"


def test_content_disposition_names_the_course(client, db_session):
    course = _seed_course(db_session)
    disposition = client.get(f"/courses/{course.id}/certificate").headers["content-disposition"]
    assert disposition == 'attachment; filename="certificate-learning-chess-fundamentals.pdf"'


def test_filename_cannot_break_out_of_the_header(client, db_session):
    course = _seed_course(db_session)
    course.title = 'Chess"; drop\r\nX-Injected: yes'
    db_session.commit()

    disposition = client.get(f"/courses/{course.id}/certificate").headers["content-disposition"]
    assert '"' not in disposition[len("attachment; filename=") + 1 : -1]
    assert "\r" not in disposition and "\n" not in disposition


def test_incomplete_course_is_400_not_500(client, db_session):
    course = _seed_course(db_session, complete=False)
    res = client.get(f"/courses/{course.id}/certificate")
    assert res.status_code == 400
    assert res.json()["detail"] == "Not all lessons are complete yet."


def test_course_with_no_lessons_is_400(client, db_session):
    course = _seed_course(db_session, lessons=0)
    res = client.get(f"/courses/{course.id}/certificate")
    assert res.status_code == 400
    assert res.json()["detail"] == "Course has no lessons."


def test_unknown_course_is_404(client):
    assert client.get("/courses/nope/certificate").status_code == 404


def test_second_request_is_served_from_cache(client, db_session):
    course = _seed_course(db_session)
    first = client.get(f"/courses/{course.id}/certificate")
    second = client.get(f"/courses/{course.id}/certificate")

    assert first.content == second.content
    row = db_session.execute(
        text("SELECT COUNT(*) AS n FROM certificate_cache WHERE course_id = :c"),
        {"c": course.id},
    ).fetchone()
    assert row.n == 1


def test_a_renderer_failure_is_503_not_an_uncaught_500(client, db_session, monkeypatch):
    """An uncaught exception escapes CORSMiddleware and reaches the browser
    with no status at all, which is how the original defect presented."""
    def boom(*_args, **_kwargs):
        raise OSError("cannot load library 'libgobject-2.0-0'")

    monkeypatch.setattr("app.services.certificates.render_certificate_pdf", boom)

    course = _seed_course(db_session)
    res = client.get(f"/courses/{course.id}/certificate")
    assert res.status_code == 503
    assert "could not be generated" in res.json()["detail"]
