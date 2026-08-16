"""Tests for practice drill generation and availability.

Every drill is derived deterministically from content_json, so none of these
need Ollama. Piper is stubbed for the listening drill.
"""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module
from app.services.drills import (
    build_mcq,
    build_order,
    build_pronounce,
    collect_concepts,
    collect_step_sets,
    drill_availability,
    load_course_lessons,
)

TTS_PATCH = "app.routes.drills.synthesize_speech"


def _content(n_concepts: int, steps: int = 4) -> str:
    return json.dumps(
        {
            "key_concepts": [
                {
                    "name": f"Concept {i}",
                    "definition": f"A sufficiently long definition for concept {i} explaining it.",
                    "example": f"example_{i}()" if i % 2 == 0 else "",
                }
                for i in range(n_concepts)
            ],
            "worked_example": "\n".join(f"Step {i}: do the thing." for i in range(steps)),
            "common_pitfalls": [],
            "practice_prompts": [],
        }
    )


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


@pytest.fixture(autouse=True)
def isolated_audio_dir(tmp_path, monkeypatch):
    """Drill audio is cached on disk; without this, a WAV written by one test
    satisfies the cache in the next and masks a synthesis failure."""
    monkeypatch.setattr("app.routes.drills._AUDIO_DIR", tmp_path)
    yield


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


def _seed(db_session, *, lesson_contents, category="Programming", goal="Learn things", title="A Course"):
    course = Course(
        goal=goal, duration="short_term", category=category, title=title, description="d"
    )
    db_session.add(course)
    db_session.flush()
    module = Module(course_id=course.id, order_index=0, title="M", description="d")
    db_session.add(module)
    db_session.flush()
    for i, content in enumerate(lesson_contents):
        db_session.add(
            Lesson(
                module_id=module.id,
                order_index=i,
                title=f"Lesson {i}",
                description="Prose summary.",
                duration_minutes=20,
                content_json=content,
            )
        )
    db_session.commit()
    db_session.refresh(course)
    return course


# ---------------------------------------------------------------------------
# Availability
# ---------------------------------------------------------------------------

def test_unenriched_course_offers_nothing_but_explains_why(client, db_session):
    course = _seed(db_session, lesson_contents=[None, None, None])
    body = client.get(f"/courses/{course.id}/drills").json()

    assert body["enriched_lessons"] == 0
    assert body["total_lessons"] == 3
    assert all(d["available"] is False for d in body["drills"])
    assert all(d["reason"] for d in body["drills"])
    mcq = next(d for d in body["drills"] if d["kind"] == "mcq")
    assert "Open a lesson" in mcq["reason"]


def test_enriched_course_offers_content_drills(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(4), None])
    drills = {d["kind"]: d for d in client.get(f"/courses/{course.id}/drills").json()["drills"]}

    assert drills["mcq"]["available"] is True
    assert drills["match"]["available"] is True
    assert drills["order"]["available"] is True
    assert drills["listen"]["available"] is True


def test_pronounce_is_language_courses_only(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(4)], category="Programming")
    drills = {d["kind"]: d for d in client.get(f"/courses/{course.id}/drills").json()["drills"]}
    assert drills["pronounce"]["available"] is False
    assert "language courses" in drills["pronounce"]["reason"]


def test_pronounce_available_for_a_language_course(client, db_session):
    course = _seed(
        db_session,
        lesson_contents=[_content(4)],
        category="Language",
        goal="Learn conversational Spanish",
        title="Spanish for Beginners",
    )
    body = client.get(f"/courses/{course.id}/drills").json()
    drills = {d["kind"]: d for d in body["drills"]}
    assert body["target_language"] == "es"
    assert drills["pronounce"]["available"] is True


def test_too_few_concepts_leaves_drills_unavailable(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(2, steps=2)])
    drills = {d["kind"]: d for d in client.get(f"/courses/{course.id}/drills").json()["drills"]}
    assert drills["mcq"]["available"] is False       # needs 3
    assert drills["match"]["available"] is False     # needs 4
    assert drills["order"]["available"] is False     # needs 3 steps


def test_availability_404s_for_unknown_course(client):
    assert client.get("/courses/nope/drills").status_code == 404


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def test_mcq_answer_is_always_among_the_options(db_session):
    course = _seed(db_session, lesson_contents=[_content(6)])
    concepts = collect_concepts(load_course_lessons(course.id, db_session))
    import random

    items = build_mcq(concepts, 6, random.Random(0))
    assert items
    for item in items:
        assert item["options"][item["answer_index"]]
        assert len(set(item["options"])) == len(item["options"]), "no duplicate options"


def test_mcq_pool_spans_lessons(db_session):
    """Distractors come from the whole course, not one lesson."""
    course = _seed(db_session, lesson_contents=[_content(2), _content(2)])
    concepts = collect_concepts(load_course_lessons(course.id, db_session))
    # Two lessons contribute concepts with identical generated names, so
    # de-duplication should collapse them.
    assert len(concepts) == 4


def test_mcq_returns_nothing_below_the_floor(db_session):
    import random

    course = _seed(db_session, lesson_contents=[_content(2)])
    concepts = collect_concepts(load_course_lessons(course.id, db_session))
    assert build_mcq(concepts, 5, random.Random(0)) == []


def test_order_shuffles_and_can_be_solved(db_session):
    import random

    course = _seed(db_session, lesson_contents=[_content(3, steps=5)])
    step_sets = collect_step_sets(load_course_lessons(course.id, db_session))
    items = build_order(step_sets, 5, random.Random(1))
    assert items
    item = items[0]
    assert item["steps"] != [f"Step {i}: do the thing." for i in range(5)], "must shuffle"
    # correct_order holds display indices in the order they belong.
    restored = [item["steps"][i] for i in item["correct_order"]]
    assert restored == [f"Step {i}: do the thing." for i in range(5)]


def test_order_skips_examples_with_too_few_steps(db_session):
    course = _seed(db_session, lesson_contents=[_content(4, steps=2)])
    assert collect_step_sets(load_course_lessons(course.id, db_session)) == []


def test_pronounce_falls_back_to_name_when_example_is_empty(db_session):
    import random

    course = _seed(db_session, lesson_contents=[_content(4)])
    concepts = collect_concepts(load_course_lessons(course.id, db_session))
    items = build_pronounce(concepts, 10, random.Random(0))
    assert items
    assert all(item["phrase"] for item in items), "empty example must fall back to the name"


def test_empty_pitfalls_and_prompts_break_nothing(db_session):
    """The enrichment validator accepts their absence, so drills must too."""
    course = _seed(db_session, lesson_contents=[_content(4)])
    lessons = load_course_lessons(course.id, db_session)
    availability = drill_availability(course, lessons)
    assert availability["drills"]


# ---------------------------------------------------------------------------
# Item endpoints
# ---------------------------------------------------------------------------

def test_get_mcq_items(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(5)])
    body = client.get(f"/courses/{course.id}/drills/mcq?n=3").json()
    assert body["kind"] == "mcq"
    assert len(body["items"]) == 3
    assert "prompt" in body["items"][0]


def test_get_drill_409s_when_content_is_insufficient(client, db_session):
    course = _seed(db_session, lesson_contents=[None])
    resp = client.get(f"/courses/{course.id}/drills/mcq")
    assert resp.status_code == 409
    assert "Open a lesson" in resp.json()["detail"]


def test_unknown_drill_kind_404s(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(4)])
    assert client.get(f"/courses/{course.id}/drills/nonsense").status_code == 404


def test_listen_never_leaks_the_spoken_text(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(5)])
    with patch(TTS_PATCH, return_value=b"RIFFfake"):
        body = client.get(f"/courses/{course.id}/drills/listen?n=3").json()

    assert body["items"]
    for item in body["items"]:
        assert "speak" not in item, "sending the text would defeat a listening drill"
        assert "prompt" not in item
        assert item["audio_url"].startswith("/audio/")
        assert item["options"][item["answer_index"]]


def test_listen_503s_when_the_voice_is_missing(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(5)])
    with patch(TTS_PATCH, side_effect=RuntimeError("voice not found")):
        resp = client.get(f"/courses/{course.id}/drills/listen")
    assert resp.status_code == 503


def test_complete_records_an_event_without_touching_cards(client, db_session):
    course = _seed(db_session, lesson_contents=[_content(4)])
    resp = client.post(f"/courses/{course.id}/drills/mcq/complete?correct=3&total=4")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Worked-example splitting
# ---------------------------------------------------------------------------

def test_split_steps_handles_newline_separated():
    from app.services.drills import split_steps

    assert len(split_steps("Step 1: a.\nStep 2: b.\nStep 3: c.")) == 3


def test_split_steps_handles_inline_markers():
    """What the model actually returns: one line of "Step 1: ... Step 2: ..."."""
    from app.services.drills import split_steps

    raw = (
        "Step 1: Open a file named 'data.txt' in read mode. "
        "Step 2: Assign the returned file object to a variable. "
        "Step 3: Call read() on it. "
        "Step 4: Close the handle."
    )
    steps = split_steps(raw)
    assert len(steps) == 4
    assert steps[0].startswith("Step 1")
    assert steps[3].startswith("Step 4")


def test_split_steps_handles_numbered_prose():
    from app.services.drills import split_steps

    assert len(split_steps("1. First thing. 2. Second thing. 3. Third thing.")) == 3


def test_split_steps_returns_few_when_there_is_no_structure():
    from app.services.drills import split_steps

    assert len(split_steps("Just one continuous explanation with no steps.")) < 3


def test_order_available_for_inline_step_content(client, db_session):
    """Regression: inline steps made the ordering drill permanently unavailable."""
    inline = json.dumps(
        {
            "key_concepts": [
                {"name": "A", "definition": "A long enough definition of the concept A.", "example": ""},
                {"name": "B", "definition": "A long enough definition of the concept B.", "example": ""},
            ],
            "worked_example": "Step 1: do this. Step 2: then this. Step 3: finally this.",
            "common_pitfalls": [],
            "practice_prompts": [],
        }
    )
    course = _seed(db_session, lesson_contents=[inline])
    drills = {d["kind"]: d for d in client.get(f"/courses/{course.id}/drills").json()["drills"]}
    assert drills["order"]["available"] is True
