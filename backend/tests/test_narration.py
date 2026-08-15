"""Tests for lesson narration text building, chunking and WAV assembly.

None of this was covered before. No Ollama and no piper are needed — TTS is
stubbed at the endpoint level and the helpers are called directly.
"""

import io
import json
import wave
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module, Objective
from app.routes.audio import _build_narration_text, _chunk_text, _concat_wavs

CONTENT = {
    "key_concepts": [
        {
            "name": "open()",
            "definition": "It returns a file object positioned at the start.",
            "example": "f = open('data.txt', 'r')",
        }
    ],
    "worked_example": "Step 1: Call open on the path.\nStep 2: Read it into a string.",
    "common_pitfalls": ["Forgetting to close the handle."],
    "practice_prompts": ["Why must you close a file?"],
}


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    # narration_cache lives in _run_migrations(), not Base.metadata, so
    # create_all() does not make it and the endpoint would die on the cache
    # SELECT with a confusing OperationalError.
    with engine.connect() as conn:
        conn.execute(
            sql_text("""
                CREATE TABLE IF NOT EXISTS narration_cache (
                    lesson_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
        )
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


def _seed_lesson(db_session, description="Files hold bytes on disk.", content_json=None) -> Lesson:
    course = Course(
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
        description=description,
        duration_minutes=45,
        content_json=content_json,
    )
    db_session.add(lesson)
    db_session.flush()
    db_session.add(
        Objective(lesson_id=lesson.id, order_index=0, description="Open a file from disk.")
    )
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# Narration text
# ---------------------------------------------------------------------------

def test_narration_omits_title_and_objectives(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    narration = _build_narration_text(lesson)
    assert "Lesson:" not in narration
    assert "Reading files" not in narration
    assert "Open a file from disk" not in narration


def test_narration_has_no_spoken_section_headers(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    narration = _build_narration_text(lesson)
    assert "Key concepts." not in narration
    assert "Worked example." not in narration
    # but the substance is there
    assert "open()" in narration
    assert "returns a file object" in narration


def test_narration_reads_content_json_not_description(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    narration = _build_narration_text(lesson)
    assert "Files hold bytes on disk." in narration
    assert "Forgetting to close the handle." in narration
    # no raw JSON must ever reach the speech synthesiser
    assert "{" not in narration
    assert "key_concepts" not in narration


def test_narration_excludes_practice_prompts(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    assert "Why must you close a file?" not in _build_narration_text(lesson)


def test_narration_falls_back_to_prose_when_unenriched(db_session):
    lesson = _seed_lesson(db_session, content_json=None)
    assert _build_narration_text(lesson) == "Files hold bytes on disk."


def test_narration_empty_when_no_content_at_all(db_session):
    lesson = _seed_lesson(db_session, description="", content_json=None)
    assert _build_narration_text(lesson) == ""


def test_narration_normalises_terminal_punctuation(db_session):
    lesson = _seed_lesson(db_session, description="No trailing period", content_json=None)
    assert _build_narration_text(lesson).endswith(".")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def test_chunk_text_empty_returns_no_chunks():
    assert _chunk_text("") == []
    assert _chunk_text("   ") == []


def test_chunk_text_short_text_is_one_chunk():
    assert len(_chunk_text("One sentence. Two sentences.")) == 1


def test_chunk_text_splits_long_text():
    long_text = " ".join(f"This is sentence number {i}." for i in range(300))
    chunks = _chunk_text(long_text, max_len=900)
    assert len(chunks) >= 3
    assert all(len(c) <= 1000 for c in chunks)
    assert "sentence number 0" in chunks[0]
    assert "sentence number 299" in chunks[-1]


# ---------------------------------------------------------------------------
# WAV assembly
# ---------------------------------------------------------------------------

def _make_wav(frames: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(22050)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


def test_concat_wavs_single_chunk_is_passthrough():
    wav = _make_wav(100)
    assert _concat_wavs([wav]) is wav


def test_concat_wavs_merges_frame_counts():
    merged = _concat_wavs([_make_wav(100), _make_wav(150)])
    with wave.open(io.BytesIO(merged), "rb") as w:
        assert w.getnframes() == 250
        assert w.getframerate() == 22050


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

def test_narration_endpoint_422_when_no_content(client, db_session):
    lesson = _seed_lesson(db_session, description="", content_json=None)
    with patch("app.routes.audio.synthesize_speech") as tts:
        resp = client.post(f"/lessons/{lesson.id}/narration")
    assert resp.status_code == 422
    tts.assert_not_called()


def test_narration_endpoint_404_for_unknown_lesson(client):
    assert client.post("/lessons/nope/narration").status_code == 404


def test_narration_endpoint_synthesises_body_content(client, db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps(CONTENT))
    with patch("app.routes.audio.synthesize_speech", return_value=_make_wav(10)) as tts:
        resp = client.post(f"/lessons/{lesson.id}/narration")
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("/audio/")
    spoken = " ".join(call.args[0] for call in tts.call_args_list)
    assert "Lesson:" not in spoken
    assert "open()" in spoken
