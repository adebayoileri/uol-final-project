"""Tests for semantic search: indexing and retrieval via content_embeddings table."""

import uuid

import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ContentEmbedding, Course, Lesson, Module
from app.services.embeddings import index_lesson, index_question, search
from tests.conftest import TEST_USER_ID

# ---------------------------------------------------------------------------
# DB / client fixtures (same pattern as test_questions.py)
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
def db_session(test_engine):
    Session = sessionmaker(bind=test_engine)
    with Session() as session:
        yield session


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
# Seed helpers
# ---------------------------------------------------------------------------

def _make_lesson(db_session, title: str, description: str, course_id: str | None = None) -> Lesson:
    cid = course_id or str(uuid.uuid4())
    course = Course(
        user_id=TEST_USER_ID,
        id=cid,
        goal="Test goal",
        duration="short_term",
        category="Test",
        title="Test Course",
        description="A test course.",
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
        title=title,
        description=description,
        duration_minutes=30,
    )
    db_session.add(course)
    db_session.commit()
    return lesson


def _owned_course(db) -> str:
    """Create a course owned by the test user and return its id.

    Embeddings are scoped through course ownership, so a free-floating uuid
    belongs to nobody and matches nothing.
    """
    course = Course(
        user_id=TEST_USER_ID,
        goal="Search fixture",
        duration="short_term",
        category="Test",
        title="Search Fixture",
        description="Fixture course.",
    )
    db.add(course)
    db.flush()
    return course.id


def _insert_embedding(db_session, content_type: str, content_id: str, text: str, course_id: str, lesson_id: str | None = None) -> None:
    vec = np.zeros(384, dtype=np.float32)
    db_session.add(ContentEmbedding(
        content_type=content_type,
        content_id=content_id,
        content_text=text,
        course_id=course_id,
        lesson_id=lesson_id,
        vector=vec.tobytes(),
    ))
    db_session.commit()


# ---------------------------------------------------------------------------
# index_lesson tests
# ---------------------------------------------------------------------------

def test_index_lesson_creates_row(db_session):
    lesson = _make_lesson(db_session, "Python Variables", "Learn to declare variables.")
    index_lesson(lesson, db_session)
    rows = db_session.query(ContentEmbedding).filter(ContentEmbedding.content_type == "lesson").all()
    assert len(rows) == 1
    assert rows[0].content_id == lesson.id
    assert rows[0].content_type == "lesson"
    assert rows[0].lesson_id is None
    assert len(rows[0].vector) == 384 * 4  # 384 float32s = 1536 bytes


def test_index_lesson_upserts_not_duplicates(db_session):
    lesson = _make_lesson(db_session, "Python Variables", "Learn to declare variables.")
    index_lesson(lesson, db_session)
    index_lesson(lesson, db_session)  # call twice
    rows = db_session.query(ContentEmbedding).all()
    assert len(rows) == 1  # still one row


def test_index_lesson_sets_course_id(db_session):
    lesson = _make_lesson(db_session, "Python Loops", "for and while loops.")
    index_lesson(lesson, db_session)
    row = db_session.query(ContentEmbedding).first()
    assert row.course_id == lesson.module.course_id


# ---------------------------------------------------------------------------
# index_question tests
# ---------------------------------------------------------------------------

def test_index_question_creates_row(db_session):
    from app.models import Question
    import json
    lesson = _make_lesson(db_session, "Python Functions", "Define and call functions.")
    q = Question(
        id=str(uuid.uuid4()),
        lesson=lesson,
        order_index=0,
        text="What is a Python function?",
        reference_answer="A reusable block of code.",
        reference_embedding=json.dumps([0.1] * 384),
    )
    db_session.add(q)
    db_session.commit()

    index_question(q, lesson, db_session)

    rows = db_session.query(ContentEmbedding).filter(ContentEmbedding.content_type == "question").all()
    assert len(rows) == 1
    assert rows[0].content_id == q.id
    assert rows[0].lesson_id == lesson.id
    assert rows[0].content_text == q.text


def test_index_question_upserts_not_duplicates(db_session):
    from app.models import Question
    import json
    lesson = _make_lesson(db_session, "Python Functions", "Define and call functions.")
    q = Question(
        id=str(uuid.uuid4()),
        lesson=lesson,
        order_index=0,
        text="What is a Python function?",
        reference_answer="A reusable block of code.",
        reference_embedding=json.dumps([0.1] * 384),
    )
    db_session.add(q)
    db_session.commit()

    index_question(q, lesson, db_session)
    index_question(q, lesson, db_session)  # twice

    assert db_session.query(ContentEmbedding).count() == 1


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------

def test_search_empty_index_returns_empty(db_session):
    results = search("Python variables", 5, db_session, TEST_USER_ID)
    assert results == []


def test_search_top_k_limit(db_session):
    cid = _owned_course(db_session)
    for i in range(10):
        _insert_embedding(db_session, "lesson", str(uuid.uuid4()), f"Lesson {i}", cid)
    results = search("lesson content", 3, db_session, TEST_USER_ID)
    assert len(results) == 3


def test_search_returns_all_when_fewer_than_k(db_session):
    cid = _owned_course(db_session)
    for i in range(3):
        _insert_embedding(db_session, "lesson", str(uuid.uuid4()), f"Lesson {i}", cid)
    results = search("lesson", 10, db_session, TEST_USER_ID)
    assert len(results) == 3


def test_search_course_id_scope(db_session):
    cid_a = _owned_course(db_session)
    cid_b = _owned_course(db_session)
    _insert_embedding(db_session, "lesson", str(uuid.uuid4()), "Python variables and types", cid_a)
    _insert_embedding(db_session, "lesson", str(uuid.uuid4()), "Spanish greetings", cid_b)

    results = search("variable types", 5, db_session, TEST_USER_ID, course_id=cid_a)
    assert len(results) == 1
    assert results[0]["course_id"] == cid_a


def test_search_scores_descending(db_session):
    cid = _owned_course(db_session)
    for i in range(5):
        _insert_embedding(db_session, "lesson", str(uuid.uuid4()), f"Topic {i}", cid)
    results = search("topic", 5, db_session, TEST_USER_ID)
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_result_shape(db_session):
    cid = _owned_course(db_session)
    lid = str(uuid.uuid4())
    _insert_embedding(db_session, "lesson", lid, "Python loops", cid)
    results = search("loops", 1, db_session, TEST_USER_ID)
    assert len(results) == 1
    r = results[0]
    assert set(r.keys()) == {"content_type", "content_id", "content_text", "course_id", "lesson_id", "score"}
    assert r["content_type"] == "lesson"
    assert r["content_id"] == lid
    assert isinstance(r["score"], float)


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

def test_search_endpoint_returns_200(client, test_engine):
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        cid = _owned_course(db)
        _insert_embedding(db, "lesson", str(uuid.uuid4()), "Python variables", cid)
    resp = client.get("/search?q=variables")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_search_endpoint_empty_q_returns_422(client):
    resp = client.get("/search?q=")
    assert resp.status_code == 422


def test_search_endpoint_k_param(client, test_engine):
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        cid = _owned_course(db)
        for i in range(8):
            _insert_embedding(db, "lesson", str(uuid.uuid4()), f"Lesson {i} about Python", cid)
    resp = client.get("/search?q=Python&k=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


def test_search_endpoint_course_id_filter(client, test_engine):
    Session = sessionmaker(bind=test_engine)
    with Session() as db:
        cid = _owned_course(db)
        _insert_embedding(db, "lesson", str(uuid.uuid4()), "Python variables", cid)
        _insert_embedding(db, "lesson", str(uuid.uuid4()), "Spanish greetings", str(uuid.uuid4()))

    resp = client.get(f"/search?q=variables&course_id={cid}")
    assert resp.status_code == 200
    data = resp.json()
    assert all(r["course_id"] == cid for r in data)


# ---------------------------------------------------------------------------
# Semantic relevance — real sentence-transformers (deterministic)
# Index a small corpus of clearly distinct topics; verify the right item ranks #1.
# ---------------------------------------------------------------------------

SEMANTIC_CORPUS = [
    ("Python loop iteration with for and while", "lesson"),
    ("Python variable assignment and data types", "lesson"),
    ("Exception handling with try except blocks", "lesson"),
    ("Object-oriented programming with classes and objects", "lesson"),
    ("Conditional statements if elif else", "lesson"),
    ("Spanish vocabulary greetings hola", "lesson"),
    ("Database SQL queries join select", "lesson"),
]


@pytest.fixture()
def semantic_db(db_session):
    # A real owned course: embeddings are now scoped through course ownership,
    # so a free-floating course_id belongs to nobody and returns nothing.
    course = Course(
        user_id=TEST_USER_ID,
        goal="Semantic corpus",
        duration="short_term",
        category="Test",
        title="Semantic Corpus",
        description="Fixture course.",
    )
    db_session.add(course)
    db_session.flush()
    cid = course.id
    from app.services.answer_evaluator import embed
    for text, ctype in SEMANTIC_CORPUS:
        vec = np.array(embed(text), dtype=np.float32)
        db_session.add(ContentEmbedding(
            content_type=ctype,
            content_id=str(uuid.uuid4()),
            content_text=text,
            course_id=cid,
            lesson_id=None,
            vector=vec.tobytes(),
        ))
    db_session.commit()
    return db_session


@pytest.mark.parametrize("query,expected_fragment", [
    ("Python loop iteration", "loop"),
    ("assigning values to variables", "variable"),
    ("handling errors and exceptions", "exception"),
    ("object oriented classes", "class"),
    ("if else conditional logic", "conditional"),
])
def test_search_semantic_relevance(semantic_db, query, expected_fragment):
    results = search(query, k=3, db=semantic_db, user_id=TEST_USER_ID)
    assert results, f"No results for query: {query!r}"
    top_text = results[0]["content_text"].lower()
    assert expected_fragment in top_text, (
        f"Query {query!r}: expected top result to contain {expected_fragment!r}, "
        f"got {results[0]['content_text']!r}"
    )
