"""Tests for question generation and answer evaluation.

Route tests: in-memory SQLite, mocked LLM and embed calls — no Ollama needed.
Evaluation fixture tests: real sentence-transformers (deterministic, cached after
first download) — no Ollama needed for the embedding path.
"""

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module, Objective, Question  # noqa: F401
from app.services.answer_evaluator import (
    CORRECT_THRESHOLD,
    INCORRECT_THRESHOLD,
    evaluate_answer,
    embed,
)

# ---------------------------------------------------------------------------
# Shared DB / client fixtures (mirrors test_courses.py)
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
# Seed helpers — insert a lesson (and its parents) into the test DB
# ---------------------------------------------------------------------------

@pytest.fixture()
def lesson_id(test_engine):
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        course = Course(
            id=str(uuid.uuid4()),
            goal="Learn Python for data science",
            duration="short_term",
            category="Programming",
            title="Python for Data Science",
            description="A short course.",
        )
        module = Module(
            id=str(uuid.uuid4()),
            course=course,
            order_index=0,
            title="Module 1",
            description="Intro module.",
        )
        lesson = Lesson(
            id=str(uuid.uuid4()),
            module=module,
            order_index=0,
            title="Variables and Types",
            description="Learn about Python variables.",
            duration_minutes=45,
        )
        obj = Objective(
            id=str(uuid.uuid4()),
            lesson=lesson,
            order_index=0,
            description="Understand Python variable assignment.",
        )
        lesson.objectives.append(obj)
        db.add(course)
        db.commit()
        lid = lesson.id
    return lid


@pytest.fixture()
def question_id(test_engine, lesson_id):
    """Insert a Question row directly, bypassing LLM/embed."""
    fake_emb = [0.1] * 384
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        q = Question(
            id=str(uuid.uuid4()),
            lesson_id=lesson_id,
            order_index=0,
            text="What is a variable in Python?",
            reference_answer="A variable is a named container that holds a value in memory.",
            reference_embedding=json.dumps(fake_emb),
        )
        db.add(q)
        db.commit()
        qid = q.id
    return qid


# ---------------------------------------------------------------------------
# Mocked LLM / embed responses
# ---------------------------------------------------------------------------

MOCK_QUESTIONS_DATA = [
    {
        "question": "What is a variable in Python?",
        "reference_answer": "A variable is a named container that holds a value in memory.",
    },
    {
        "question": "Name two built-in Python data types.",
        "reference_answer": "Python has many built-in types, including int, float, str, and bool.",
    },
    {
        "question": "How do you assign a value to a variable?",
        "reference_answer": "Use the assignment operator: x = 42.",
    },
]

FAKE_EMBEDDING = [0.1] * 384

GEN_PATCH = "app.routes.lessons.generate_questions"
EMBED_PATCH = "app.routes.lessons.embed"
EVAL_PATCH = "app.routes.questions.evaluate_answer"


# ---------------------------------------------------------------------------
# Route: POST /lessons/{id}/questions/generate
# ---------------------------------------------------------------------------

def test_generate_questions_returns_201(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        response = client.post(f"/lessons/{lesson_id}/questions/generate")

    assert response.status_code == 201


def test_generate_questions_count(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        data = client.post(f"/lessons/{lesson_id}/questions/generate").json()

    assert len(data) == 3


def test_generate_questions_response_shape(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        data = client.post(f"/lessons/{lesson_id}/questions/generate").json()

    first = data[0]
    assert "id" in first
    assert "order_index" in first
    assert first["text"] == MOCK_QUESTIONS_DATA[0]["question"]
    assert first["reference_answer"] == MOCK_QUESTIONS_DATA[0]["reference_answer"]
    assert "created_at" in first
    assert "reference_embedding" not in first  # internal — must not leak


def test_generate_questions_order_index(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        data = client.post(f"/lessons/{lesson_id}/questions/generate").json()

    assert [q["order_index"] for q in data] == [0, 1, 2]


def test_generate_questions_persisted(client, lesson_id, test_engine):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        client.post(f"/lessons/{lesson_id}/questions/generate")

    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        assert db.query(Question).count() == 3


def test_generate_questions_lesson_not_found(client):
    response = client.post(f"/lessons/{uuid.uuid4()}/questions/generate")
    assert response.status_code == 404


def test_generate_questions_ollama_down_503(client, lesson_id):
    with patch(GEN_PATCH, side_effect=RuntimeError("Ollama unreachable")):
        response = client.post(f"/lessons/{lesson_id}/questions/generate")

    assert response.status_code == 503


# ---------------------------------------------------------------------------
# Route: GET /lessons/{id}/questions
# ---------------------------------------------------------------------------

def test_get_questions_empty(client, lesson_id):
    response = client.get(f"/lessons/{lesson_id}/questions")
    assert response.status_code == 200
    assert response.json() == []


def test_get_questions_returns_persisted(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        client.post(f"/lessons/{lesson_id}/questions/generate")

    response = client.get(f"/lessons/{lesson_id}/questions")
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_questions_ordered(client, lesson_id):
    with patch(GEN_PATCH, return_value=MOCK_QUESTIONS_DATA), \
         patch(EMBED_PATCH, return_value=FAKE_EMBEDDING):
        client.post(f"/lessons/{lesson_id}/questions/generate")

    data = client.get(f"/lessons/{lesson_id}/questions").json()
    assert [q["order_index"] for q in data] == [0, 1, 2]


def test_get_questions_lesson_not_found(client):
    response = client.get(f"/lessons/{uuid.uuid4()}/questions")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Route: POST /questions/{id}/answer
# ---------------------------------------------------------------------------

def test_answer_correct_verdict(client, question_id):
    with patch(EVAL_PATCH, return_value={"verdict": "correct", "score": 0.82, "signal_used": "embedding"}):
        response = client.post(
            f"/questions/{question_id}/answer",
            json={"answer": "A variable stores a value."},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "correct"
    assert data["signal_used"] == "embedding"
    assert isinstance(data["score"], float)


def test_answer_incorrect_verdict(client, question_id):
    with patch(EVAL_PATCH, return_value={"verdict": "incorrect", "score": 0.12, "signal_used": "embedding"}):
        response = client.post(
            f"/questions/{question_id}/answer",
            json={"answer": "A variable is a type of loop."},
        )

    assert response.status_code == 200
    assert response.json()["verdict"] == "incorrect"


def test_answer_embedding_plus_llm_signal(client, question_id):
    with patch(EVAL_PATCH, return_value={"verdict": "correct", "score": 0.51, "signal_used": "embedding+llm"}):
        response = client.post(
            f"/questions/{question_id}/answer",
            json={"answer": "Python variables hold values."},
        )

    assert response.json()["signal_used"] == "embedding+llm"


def test_answer_question_not_found(client):
    response = client.post(
        f"/questions/{uuid.uuid4()}/answer",
        json={"answer": "Some answer"},
    )
    assert response.status_code == 404


def test_answer_empty_string_returns_422(client, question_id):
    response = client.post(
        f"/questions/{question_id}/answer",
        json={"answer": ""},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# Evaluation fixture — real sentence-transformers, no Ollama
#
# Validates that the chosen thresholds (0.35 / 0.65) achieve ≥ 80% precision
# on "correct" verdicts across a diverse set of Q&A pairs.
# ---------------------------------------------------------------------------

# Fixture design notes:
#
# Embeddings excel at detecting TOPIC distance (cross-domain), not factual
# correctness within a domain. "Paris is the capital of Germany" scores ~0.90
# cosine similarity with "Paris is the capital of France" — both are about Paris
# being a European capital. That's the grey zone the LLM fallback handles.
#
# This fixture tests the embedding-only path:
#   - CORRECT pairs: paraphrases / synonyms → score well above CORRECT_THRESHOLD
#   - INCORRECT pairs: off-topic non-answers → score well below INCORRECT_THRESHOLD
#
# Factually-wrong-but-related answers (same topic, wrong fact) are deliberately
# excluded here; they belong in integration tests that exercise the LLM path.

EVAL_FIXTURE = [
    # (user_answer, reference_answer, expected_verdict)
    # --- CORRECT: paraphrases within the same domain (9 pairs) ---
    (
        "Python is a high-level programming language",
        "Python is an interpreted, high-level, general-purpose programming language",
        "correct",
    ),
    (
        "Variables store data in memory",
        "A variable is a named container that holds a value in memory",
        "correct",
    ),
    (
        "A list is a mutable sequence in Python",
        "Lists are ordered, mutable collections in Python",
        "correct",
    ),
    (
        "Functions let you reuse blocks of code",
        "A function is a reusable block of code that performs a specific task",
        "correct",
    ),
    (
        "Machine learning algorithms learn patterns from data",
        "Machine learning is a subset of AI where algorithms learn patterns from data",
        "correct",
    ),
    (
        "Loops repeat code multiple times",
        "A loop is a control structure that repeats a block of code until a condition is met",
        "correct",
    ),
    (
        "OOP organises code into classes and objects",
        "Object-oriented programming structures code around objects that bundle data and behaviour",
        "correct",
    ),
    (
        "HTTP uses port 80 by default",
        "The default port for HTTP traffic is 80",
        "correct",
    ),
    (
        "A REST API is stateless",
        "RESTful APIs are stateless — each request contains all the information needed to process it",
        "correct",
    ),
    # --- INCORRECT: completely off-topic answers (7 pairs) ---
    # Cross-domain non-answers that have no semantic overlap with the reference.
    (
        "I enjoy reading books in the evening",
        "Python is an interpreted, high-level, general-purpose programming language",
        "incorrect",
    ),
    (
        "The solar system has eight planets",
        "A variable is a named container that holds a value in memory",
        "incorrect",
    ),
    (
        "Coffee is my favourite morning beverage",
        "Lists are ordered, mutable collections in Python",
        "incorrect",
    ),
    (
        "The Eiffel Tower is located in Paris France",
        "A function is a reusable block of code that performs a specific task",
        "incorrect",
    ),
    (
        "Photosynthesis converts sunlight into energy in plants",
        "Machine learning is a subset of AI where algorithms learn patterns from data",
        "incorrect",
    ),
    (
        "I went to the grocery store yesterday afternoon",
        "A loop is a control structure that repeats a block of code until a condition is met",
        "incorrect",
    ),
    (
        "The Atlantic Ocean separates Europe and Africa from the Americas",
        "Object-oriented programming structures code around objects that bundle data and behaviour",
        "incorrect",
    ),
]


def _embedding_only_verdict(user_answer: str, reference_answer: str) -> str:
    """Run evaluate_answer but short-circuit LLM calls in the grey zone.

    For fixture testing we only want to validate the embedding signal. Grey-zone
    cases that would normally trigger an LLM call are patched to return 'correct'
    (the evaluator's own default when LLM is unreachable) so we test precision
    only on the embedding-confident band.
    """
    ref_emb = embed(reference_answer)
    with patch(
        "app.services.answer_evaluator._llm_verify",
        return_value=True,
    ):
        result = evaluate_answer(
            question_text="(fixture)",
            user_answer=user_answer,
            reference_answer=reference_answer,
            reference_embedding=ref_emb,
        )
    return result["verdict"]


def test_eval_fixture_minimum_count():
    assert len(EVAL_FIXTURE) >= 15


def test_eval_fixture_correct_precision():
    """Precision on 'correct' verdict must be ≥ 80%."""
    true_positives = 0
    false_positives = 0

    for user_answer, reference_answer, expected in EVAL_FIXTURE:
        predicted = _embedding_only_verdict(user_answer, reference_answer)
        if predicted == "correct":
            if expected == "correct":
                true_positives += 1
            else:
                false_positives += 1

    total_predicted_correct = true_positives + false_positives
    if total_predicted_correct == 0:
        pytest.fail("Evaluator never returned 'correct' — thresholds may be too high")

    precision = true_positives / total_predicted_correct
    assert precision >= 0.80, (
        f"Correct-verdict precision {precision:.0%} is below 80% "
        f"(TP={true_positives}, FP={false_positives})"
    )


def test_eval_fixture_all_correct_pairs_pass():
    """Every 'correct' reference pair must be predicted correct OR grey-zone (not outright wrong)."""
    false_negatives = []
    for user_answer, reference_answer, expected in EVAL_FIXTURE:
        if expected != "correct":
            continue
        ref_emb = embed(reference_answer)
        from app.services.answer_evaluator import cosine_similarity
        score = cosine_similarity(embed(user_answer), ref_emb)
        # A score above INCORRECT_THRESHOLD means the model at least considers it
        # ambiguous rather than clearly wrong.
        if score <= INCORRECT_THRESHOLD:
            false_negatives.append((user_answer, reference_answer, score))

    assert not false_negatives, (
        f"These 'correct' pairs scored ≤ {INCORRECT_THRESHOLD} (clearly wrong band):\n"
        + "\n".join(f"  score={s:.3f}: {u!r}" for u, r, s in false_negatives)
    )
