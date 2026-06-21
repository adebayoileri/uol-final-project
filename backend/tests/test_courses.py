"""Tests for POST /courses.

All tests use an in-memory SQLite database and mock generate_course so
no running Ollama instance is required.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Module, Lesson, Objective  # noqa: F401 — registers models with Base

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


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

SHORT_TERM_BODY = {
    "goal": "Learn Python to automate repetitive tasks at work",
    "duration": "short_term",
    "category": "Programming",
}

LONG_TERM_BODY = {
    "goal": "Become proficient in machine learning and deploy models independently",
    "duration": "long_term",
    "category": "Data Science",
}


def _make_llm_response(num_modules: int = 2, lessons_per_module: int = 3) -> dict:
    """Build a minimal but structurally complete LLM response dict."""
    return {
        "title": "Test Course",
        "description": "A test course description.",
        "modules": [
            {
                "title": f"Module {m + 1}",
                "description": f"Description for module {m + 1}.",
                "lessons": [
                    {
                        "title": f"Lesson {m + 1}.{l + 1}",
                        "description": f"Description for lesson {l + 1}.",
                        "duration_minutes": 45,
                        "objectives": [
                            f"Objective A of lesson {m + 1}.{l + 1}.",
                            f"Objective B of lesson {m + 1}.{l + 1}.",
                        ],
                    }
                    for l in range(lessons_per_module)
                ],
            }
            for m in range(num_modules)
        ],
    }


MOCK_RESPONSE = _make_llm_response(num_modules=2, lessons_per_module=3)
PATCH_TARGET = "app.routes.courses.generate_course"


# ---------------------------------------------------------------------------
# Happy path — response shape
# ---------------------------------------------------------------------------

def test_create_course_returns_201(client):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        response = client.post("/courses", json=SHORT_TERM_BODY)

    assert response.status_code == 201


def test_response_contains_top_level_fields(client):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        data = client.post("/courses", json=SHORT_TERM_BODY).json()

    assert data["goal"] == SHORT_TERM_BODY["goal"]
    assert data["duration"] == "short_term"
    assert data["category"] == "Programming"
    assert data["title"] == "Test Course"
    assert data["description"] == "A test course description."
    assert "id" in data
    assert "created_at" in data


def test_response_modules_structure(client):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        data = client.post("/courses", json=SHORT_TERM_BODY).json()

    assert len(data["modules"]) == 2
    first_module = data["modules"][0]
    assert first_module["title"] == "Module 1"
    assert first_module["order_index"] == 0
    assert "id" in first_module


def test_response_lessons_structure(client):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        data = client.post("/courses", json=SHORT_TERM_BODY).json()

    lessons = data["modules"][0]["lessons"]
    assert len(lessons) == 3
    assert lessons[0]["order_index"] == 0
    assert lessons[0]["duration_minutes"] == 45
    assert "id" in lessons[0]


def test_response_objectives_structure(client):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        data = client.post("/courses", json=SHORT_TERM_BODY).json()

    objectives = data["modules"][0]["lessons"][0]["objectives"]
    assert len(objectives) == 2
    assert objectives[0]["order_index"] == 0
    assert objectives[1]["order_index"] == 1
    assert "id" in objectives[0]
    assert "description" in objectives[0]


def test_long_term_course_returns_201(client):
    long_term_mock = _make_llm_response(num_modules=9, lessons_per_module=4)
    with patch(PATCH_TARGET, return_value=long_term_mock):
        response = client.post("/courses", json=LONG_TERM_BODY)

    assert response.status_code == 201
    assert len(response.json()["modules"]) == 9


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

def test_course_row_persisted(client, test_engine):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        client.post("/courses", json=SHORT_TERM_BODY)

    Session = sessionmaker(bind=test_engine)
    with Session() as session:
        courses = session.query(Course).all()
    assert len(courses) == 1
    assert courses[0].goal == SHORT_TERM_BODY["goal"]
    assert courses[0].duration == "short_term"


def test_nested_records_persisted(client, test_engine):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        client.post("/courses", json=SHORT_TERM_BODY)

    Session = sessionmaker(bind=test_engine)
    with Session() as session:
        assert session.query(Module).count() == 2
        assert session.query(Lesson).count() == 6   # 2 modules × 3 lessons
        assert session.query(Objective).count() == 12  # 6 lessons × 2 objectives


def test_multiple_courses_are_independent(client, test_engine):
    with patch(PATCH_TARGET, return_value=MOCK_RESPONSE):
        r1 = client.post("/courses", json=SHORT_TERM_BODY)
        r2 = client.post("/courses", json=LONG_TERM_BODY)

    assert r1.json()["id"] != r2.json()["id"]

    Session = sessionmaker(bind=test_engine)
    with Session() as session:
        assert session.query(Course).count() == 2


# ---------------------------------------------------------------------------
# Validation — 422 errors
# ---------------------------------------------------------------------------

def test_invalid_duration_returns_422(client):
    body = {**SHORT_TERM_BODY, "duration": "weekly"}
    response = client.post("/courses", json=body)
    assert response.status_code == 422


def test_goal_too_short_returns_422(client):
    body = {**SHORT_TERM_BODY, "goal": "Python"}  # under min_length=10
    response = client.post("/courses", json=body)
    assert response.status_code == 422


def test_missing_category_returns_422(client):
    body = {"goal": SHORT_TERM_BODY["goal"], "duration": "short_term"}
    response = client.post("/courses", json=body)
    assert response.status_code == 422


def test_missing_goal_returns_422(client):
    body = {"duration": "short_term", "category": "Programming"}
    response = client.post("/courses", json=body)
    assert response.status_code == 422


def test_missing_duration_returns_422(client):
    body = {"goal": SHORT_TERM_BODY["goal"], "category": "Programming"}
    response = client.post("/courses", json=body)
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Error handling — 503 when Ollama is unavailable
# ---------------------------------------------------------------------------

def test_ollama_unreachable_returns_503(client):
    with patch(PATCH_TARGET, side_effect=RuntimeError("Cannot reach Ollama")):
        response = client.post("/courses", json=SHORT_TERM_BODY)

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()


def test_no_db_write_on_503(client, test_engine):
    with patch(PATCH_TARGET, side_effect=RuntimeError("Cannot reach Ollama")):
        client.post("/courses", json=SHORT_TERM_BODY)

    Session = sessionmaker(bind=test_engine)
    with Session() as session:
        assert session.query(Course).count() == 0
