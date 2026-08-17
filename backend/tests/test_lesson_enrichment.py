"""Tests for lazy per-lesson content enrichment.

Stubs the module-local _call_ollama (same approach as test_questions.py) so no
live Ollama is needed anywhere.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module, Objective
from app.services.lesson_enricher import (
    _build_prompt,
    _extract_object,
    generate_lesson_content,
)
from tests.conftest import TEST_USER_ID

ENRICH_PATCH = "app.services.lesson_enricher._call_ollama"

_LONG_DEF = (
    "It opens a path and returns a file object positioned at the start, "
    "holding an OS-level handle until it is closed."
)

VALID_CONTENT = {
    "key_concepts": [
        {"name": "open()", "definition": _LONG_DEF, "example": "f = open('data.txt', 'r')"},
        {"name": "read()", "definition": _LONG_DEF, "example": "text = f.read()"},
        {"name": "close()", "definition": _LONG_DEF, "example": "f.close()"},
    ],
    "worked_example": (
        "Step 1: Call open('scores.txt', 'r') to get a file object. "
        "Step 2: Call read() on it, which returns the whole file as one string. "
        "Step 3: Split that string on newlines to get one entry per line. "
        "Step 4: Call close() to release the handle and flush any buffers."
    ),
    "common_pitfalls": [
        "Forgetting to close the file, so the buffer is never flushed.",
        "Calling read() twice and getting an empty string the second time.",
    ],
    "practice_prompts": [
        "What happens if you call read() twice on the same handle?",
        "Why does forgetting close() risk losing the last write?",
    ],
}
VALID_RAW = json.dumps(VALID_CONTENT)


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
    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    db = TestingSession()
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


def _seed_lesson(db_session, content_json: str | None = None) -> Lesson:
    course = Course(
        user_id=TEST_USER_ID,
        goal="Learn Python file handling",
        duration="short_term",
        category="Programming",
        title="Python Files",
        description="A short course.",
    )
    db_session.add(course)
    db_session.flush()

    module = Module(course_id=course.id, order_index=0, title="Basics", description="Basics.")
    db_session.add(module)
    db_session.flush()

    lesson = Lesson(
        module_id=module.id,
        order_index=0,
        title="Reading files",
        description="Content for open() and read().",
        duration_minutes=45,
        content_json=content_json,
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.add(
        Objective(lesson_id=lesson.id, order_index=0, description="Read a file from disk.")
    )
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# Prompt + parsing
# ---------------------------------------------------------------------------

def test_build_prompt_formats_without_error(db_session):
    """Guards the {{/}} escaping — an unescaped brace fails at import time."""
    lesson = _seed_lesson(db_session)
    prompt = _build_prompt(lesson)
    assert "Reading files" in prompt
    assert "Learn Python file handling" in prompt
    assert "Read a file from disk." in prompt


def test_extract_object_strips_markdown_fences():
    obj = _extract_object(f"```json\n{VALID_RAW}\n```")
    assert obj["key_concepts"][0]["name"] == "open()"


def test_extract_object_ignores_prose_around_object():
    obj = _extract_object(f"Here you go:\n{VALID_RAW}\nHope that helps!")
    assert len(obj["key_concepts"]) == 3


def test_generate_parses_valid_response(db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, return_value=VALID_RAW):
        content = generate_lesson_content(lesson)
    assert set(content) == {
        "key_concepts",
        "worked_example",
        "common_pitfalls",
        "practice_prompts",
    }
    assert len(content["key_concepts"]) == 3
    assert set(content["key_concepts"][0]) == {"name", "definition", "example"}


def test_generate_retries_once_then_succeeds(db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, side_effect=["not json at all", VALID_RAW]) as m:
        content = generate_lesson_content(lesson)
    assert m.call_count == 2
    assert len(content["key_concepts"]) == 3


def test_generate_raises_after_two_bad_responses(db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, side_effect=["nope", "still nope"]) as m:
        with pytest.raises(RuntimeError):
            generate_lesson_content(lesson)
    assert m.call_count == 2


def test_generate_rejects_thin_content(db_session):
    """The anti-shallowness gate: schema-valid but shallow output is rejected."""
    lesson = _seed_lesson(db_session)
    thin = json.dumps(
        {
            "key_concepts": [{"name": "open()", "definition": "Opens a file.", "example": "f=open()"}],
            "worked_example": "Step 1: open it.",
            "common_pitfalls": [],
            "practice_prompts": [],
        }
    )
    with patch(ENRICH_PATCH, side_effect=[thin, thin]) as m:
        with pytest.raises(RuntimeError):
            generate_lesson_content(lesson)
    assert m.call_count == 2


def test_generate_does_not_retry_on_transport_error(db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, side_effect=httpx.ConnectError("refused")) as m:
        with pytest.raises(RuntimeError):
            generate_lesson_content(lesson)
    assert m.call_count == 1


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def test_enrich_endpoint_persists_content_json(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, return_value=VALID_RAW):
        resp = client.post(f"/lessons/{lesson.id}/enrich")
    assert resp.status_code == 200
    assert resp.json()["status"] == "generated"

    db_session.expire_all()
    stored = db_session.get(Lesson, lesson.id)
    assert stored.content_json is not None
    assert json.loads(stored.content_json)["key_concepts"][0]["name"] == "open()"


def test_enrich_endpoint_is_idempotent(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(ENRICH_PATCH, return_value=VALID_RAW) as m:
        first = client.post(f"/lessons/{lesson.id}/enrich")
        second = client.post(f"/lessons/{lesson.id}/enrich")
    assert m.call_count == 1
    assert first.json()["status"] == "generated"
    assert second.json()["status"] == "cached"
    assert first.json()["content"] == second.json()["content"]


def test_enrich_failure_leaves_null_and_lesson_detail_still_works(client, db_session):
    """The reader must never be blocked by an enrichment failure."""
    lesson = _seed_lesson(db_session)
    course_id = lesson.module.course_id

    with patch(ENRICH_PATCH, side_effect=httpx.ConnectError("refused")):
        resp = client.post(f"/lessons/{lesson.id}/enrich")
    assert resp.status_code == 503

    db_session.expire_all()
    assert db_session.get(Lesson, lesson.id).content_json is None

    detail = client.get(f"/courses/{course_id}/lessons/{lesson.id}")
    assert detail.status_code == 200
    assert detail.json()["content"] is None
    assert detail.json()["description"] == "Content for open() and read()."


def test_enrich_endpoint_404_for_unknown_lesson(client):
    assert client.post("/lessons/does-not-exist/enrich").status_code == 404


def test_lesson_detail_exposes_content_when_enriched(client, db_session):
    lesson = _seed_lesson(db_session, content_json=VALID_RAW)
    course_id = lesson.module.course_id

    body = client.get(f"/courses/{course_id}/lessons/{lesson.id}").json()
    assert body["content"]["key_concepts"][0]["name"] == "open()"
    assert len(body["content"]["common_pitfalls"]) == 2
    # description stays prose — question prompts and search depend on it
    assert body["description"] == "Content for open() and read()."


def test_lesson_detail_content_null_when_not_enriched(client, db_session):
    lesson = _seed_lesson(db_session)
    course_id = lesson.module.course_id
    assert client.get(f"/courses/{course_id}/lessons/{lesson.id}").json()["content"] is None


def test_concurrent_enrich_generates_once(client, db_session):
    """Two simultaneous opens must not both pay for generation."""
    import time

    lesson = _seed_lesson(db_session)

    def slow(_prompt):
        time.sleep(0.3)
        return VALID_RAW

    with patch(ENRICH_PATCH, side_effect=slow) as m:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(client.post, f"/lessons/{lesson.id}/enrich") for _ in range(2)
            ]
            responses = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in responses)
    assert m.call_count == 1
