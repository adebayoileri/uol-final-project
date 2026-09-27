"""Tests for generated listening clues.

Clue generation is the one generated field whose correctness is *negative*: a
clue is defined partly by a sentence it must not contain. The validator tests in
`test_clue_spec.py` cover that rule; these cover the call that produces the text,
the cache that holds it, and the two places it must never appear — the response
to the endpoint that generates it, and the lesson detail payload.

Stubs the module-local `_call_ollama`, the same approach as test_diagrams.
"""

import json
import time
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
from app.models import Course, Lesson, Module
from app.services.clue_generator import _build_prompt, ensure_clues, generate_clues
from tests.conftest import TEST_USER_ID

CLUE_PATCH = "app.services.clue_generator._call_ollama"

_LONG_DEF = (
    "It describes a mechanism that changes what the model does, when the "
    "mechanism applies, and why it behaves that way in practice."
)

CONCEPTS = ["Overfitting", "Classification Threshold", "Confusion Matrix"]

LESSON_CONTENT = json.dumps({
    "key_concepts": [
        {"name": name, "definition": _LONG_DEF, "example": ""} for name in CONCEPTS
    ],
    "worked_example": "Step 1: do a thing.\nStep 2: do another.\nStep 3: finish.",
    "common_pitfalls": [],
    "practice_prompts": [],
})

# Every clue below is written the way the real feature needs them: the mechanism,
# with the concept's own term — and every other concept's term — absent.
CLUES = {
    "Overfitting": (
        "A model has memorised its training data, including its noise, so it "
        "scores well on what it has seen and poorly on anything new."
    ),
    "Classification Threshold": (
        "A value that input scores have to cross before the model commits to "
        "one outcome rather than the other."
    ),
    "Confusion Matrix": (
        "A table that lays out where the errors sit, so you can see which "
        "categories get mixed up with which."
    ),
}


def _wrap(clues: dict[str, str] | None = None) -> str:
    return json.dumps({"clues": clues if clues is not None else CLUES})


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


def _seed_lesson(db_session, content_json: str | None = LESSON_CONTENT) -> Lesson:
    course = Course(
        user_id=TEST_USER_ID,
        goal="Understand how models fail",
        duration="short_term",
        category="Data science",
        title="Model Evaluation",
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
        title="Measuring error",
        description="How to tell a model is wrong.",
        duration_minutes=45,
        content_json=content_json,
    )
    db_session.add(lesson)
    db_session.commit()
    db_session.refresh(lesson)
    return lesson


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

def test_build_prompt_formats_without_error(db_session):
    """Guards the {{/}} escaping — an unescaped brace fails at import time."""
    lesson = _seed_lesson(db_session)
    prompt = _build_prompt(lesson)
    assert "Measuring error" in prompt
    assert "Understand how models fail" in prompt
    # Every concept must reach the model, or it writes clues for the wrong terms.
    for name in CONCEPTS:
        assert name in prompt


def test_build_prompt_survives_an_unenriched_lesson(db_session):
    """`clue_lock` and the route both guard this, but the prompt must not be the
    thing that raises: it is also called directly by the backfill script."""
    lesson = _seed_lesson(db_session, content_json=None)
    assert "no structured content" in _build_prompt(lesson)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def test_generate_returns_validated_clues(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value=_wrap()):
        clues = generate_clues(lesson)
    assert clues == CLUES


def test_generate_retries_then_succeeds(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, side_effect=["not json at all", _wrap()]) as mock:
        clues = generate_clues(lesson)
    assert mock.call_count == 2
    assert clues["Overfitting"] == CLUES["Overfitting"]


def test_a_leaky_clue_burns_a_retry_rather_than_being_stored(db_session):
    """The whole point of the check: the model naming its own term is a failure,
    not a cosmetic flaw to be stored and spoken."""
    lesson = _seed_lesson(db_session)
    leaky = _wrap({name: f"This is what {name} means, described at length for the listener." for name in CONCEPTS})
    with patch(CLUE_PATCH, side_effect=[leaky, _wrap()]) as mock:
        clues = generate_clues(lesson)
    assert mock.call_count == 2
    assert clues == CLUES


def test_generate_gives_up_after_two_attempts(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value="still not json"):
        with pytest.raises(RuntimeError, match="after 2 attempts"):
            generate_clues(lesson)


def test_generate_fails_rather_than_storing_a_partial_set(db_session):
    """One leaked clue must not silently cost the learner that question forever.

    A single leak in an otherwise valid response is dropped by the validator and
    the rest are kept, so what must not happen is the *only* rendered clue being
    the leaky one.
    """
    lesson = _seed_lesson(db_session)
    only_leaky = _wrap({"Overfitting": "This is overfitting, quite plainly."})
    with patch(CLUE_PATCH, return_value=only_leaky):
        with pytest.raises(RuntimeError, match="after 2 attempts"):
            generate_clues(lesson)


def test_generate_refuses_a_lesson_with_no_concepts(db_session):
    lesson = _seed_lesson(db_session, content_json=json.dumps({
        "key_concepts": [],
        "worked_example": "Step 1: nothing.",
        "common_pitfalls": [],
        "practice_prompts": [],
    }))
    with patch(CLUE_PATCH) as mock:
        with pytest.raises(RuntimeError, match="no concepts"):
            generate_clues(lesson)
    mock.assert_not_called()


def test_transport_error_is_not_retried(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, side_effect=httpx.ConnectError("refused")) as mock:
        with pytest.raises(RuntimeError, match="Cannot reach Ollama"):
            generate_clues(lesson)
    assert mock.call_count == 1


def test_an_http_error_reports_the_status(db_session):
    lesson = _seed_lesson(db_session)
    response = httpx.Response(500, request=httpx.Request("POST", "http://localhost"))
    with patch(CLUE_PATCH, side_effect=httpx.HTTPStatusError(
        "boom", request=response.request, response=response
    )):
        with pytest.raises(RuntimeError, match="HTTP 500"):
            generate_clues(lesson)


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

def test_ensure_clues_returns_the_cached_set_without_calling_ollama(db_session):
    lesson = _seed_lesson(db_session)
    lesson.clues_json = json.dumps({"clues": CLUES})
    db_session.commit()

    with patch(CLUE_PATCH) as mock:
        cues = ensure_clues(lesson, db_session)

    mock.assert_not_called()
    assert cues == {name.casefold(): clue for name, clue in CLUES.items()}


def test_ensure_clues_returns_none_and_leaves_the_column_null_on_failure(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value="garbage"):
        assert ensure_clues(lesson, db_session) is None

    db_session.expire_all()
    assert db_session.get(Lesson, lesson.id).clues_json is None


def test_ensure_clues_stores_the_mapping_the_property_reads(db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value=_wrap()):
        ensure_clues(lesson, db_session)

    db_session.expire_all()
    stored = db_session.get(Lesson, lesson.id)
    assert json.loads(stored.clues_json) == {"clues": CLUES}
    assert stored.clues["overfitting"] == CLUES["Overfitting"]


# ---------------------------------------------------------------------------
# The endpoint
# ---------------------------------------------------------------------------

def test_endpoint_generates_then_caches(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value=_wrap()) as mock:
        first = client.post(f"/lessons/{lesson.id}/clues")
        second = client.post(f"/lessons/{lesson.id}/clues")

    assert first.status_code == 200
    assert first.json() == {"status": "generated"}
    assert second.json() == {"status": "cached"}
    assert mock.call_count == 1


def test_the_endpoint_never_returns_the_clue_text(client, db_session):
    """The clue is the question. A client that can read it does not have to
    listen, which is the entire bug this feature exists to avoid."""
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value=_wrap()):
        res = client.post(f"/lessons/{lesson.id}/clues")

    body = res.text
    for clue in CLUES.values():
        assert clue not in body
    assert "clue" not in res.json()


def test_failure_is_503_and_the_next_open_retries(client, db_session):
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value="garbage"):
        assert client.post(f"/lessons/{lesson.id}/clues").status_code == 503

    db_session.expire_all()
    assert db_session.get(Lesson, lesson.id).clues_json is None

    with patch(CLUE_PATCH, return_value=_wrap()):
        assert client.post(f"/lessons/{lesson.id}/clues").json()["status"] == "generated"


def test_unenriched_lesson_is_409_and_ollama_is_not_called(client, db_session):
    lesson = _seed_lesson(db_session, content_json=None)
    with patch(CLUE_PATCH) as mock:
        res = client.post(f"/lessons/{lesson.id}/clues")
    assert res.status_code == 409
    assert "content generated" in res.json()["detail"]
    mock.assert_not_called()


def test_unknown_lesson_is_404(client):
    assert client.post("/lessons/does-not-exist/clues").status_code == 404


def test_concurrent_requests_generate_once(client, db_session):
    """Two lesson opens in flight must not both pay for a generation."""
    lesson = _seed_lesson(db_session)

    def slow(_prompt):
        time.sleep(0.15)
        return _wrap()

    with patch(CLUE_PATCH, side_effect=slow) as mock:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(client.post, f"/lessons/{lesson.id}/clues") for _ in range(2)
            ]
            results = [f.result() for f in futures]

    assert all(r.status_code == 200 for r in results)
    assert mock.call_count == 1


def test_the_lesson_detail_payload_never_carries_a_clue(client, db_session):
    """The other place a clue could leak. `LessonDetailResponse` enumerates its
    fields, so this is structural — the test pins it so a later change that
    widened the schema to `dict` would fail here rather than in the drill."""
    lesson = _seed_lesson(db_session)
    with patch(CLUE_PATCH, return_value=_wrap()):
        client.post(f"/lessons/{lesson.id}/clues")

    detail = client.get(f"/courses/{lesson.module.course_id}/lessons/{lesson.id}").text
    for clue in CLUES.values():
        assert clue not in detail
