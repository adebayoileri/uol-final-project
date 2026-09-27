"""Tests for the category vocabulary and the Auto classifier.

No Ollama is required: `_request_model` is patched wherever a model answer is
needed, which is also what lets the failure paths be tested at all — an
unreachable model is the case that matters most and the one a live call cannot
produce on demand.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Course, Lesson, Module, Objective  # noqa: F401 — registers models
from app.services.categorizer import (
    AUTO,
    CATEGORIES,
    CATEGORY_VALUES,
    FALLBACK_CATEGORY,
    resolve_category,
    suggest_category,
)
from app.services.course_profile import LANGUAGE_KEYWORDS, resolve_course_profile

REQUEST_TARGET = "app.services.categorizer._request_model"


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


def _course(category: str, goal: str = "", title: str = "") -> SimpleNamespace:
    """A stand-in course. The resolver reads attributes, never a session."""
    return SimpleNamespace(goal=goal, category=category, title=title)


def _model_says(value: str) -> str:
    """A raw model response, as `_request_model` would return it."""
    return '{"category": "%s"}' % value


# ---------------------------------------------------------------------------
# Vocabulary integrity
# ---------------------------------------------------------------------------

def test_category_values_are_unique():
    """Two entries with one value would make the dropdown store whichever the
    lookup happened to find first."""
    values = [c.value for c in CATEGORIES]
    assert len(values) == len(set(values))


def test_every_category_has_a_group_and_a_label():
    for category in CATEGORIES:
        assert category.group, f"{category.value} has no group"
        assert category.display, f"{category.value} has no label"


def test_fallback_category_is_in_the_vocabulary():
    assert FALLBACK_CATEGORY in CATEGORY_VALUES


# ---------------------------------------------------------------------------
# The vocabulary and the resolver must agree
#
# This is the claim the whole module rests on: a value the dropdown offers is a
# value `course_profile` recognises, so choosing from the list cannot produce the
# mismatch the resolver was written to absorb.
# ---------------------------------------------------------------------------

def test_every_language_category_resolves_to_its_language():
    expected = {
        LANGUAGE_KEYWORDS[code][0].title(): code for code in LANGUAGE_KEYWORDS
    }
    language_categories = [c.value for c in CATEGORIES if c.group == "Languages"]

    assert set(language_categories) == set(expected), (
        "language categories and the resolver's keyword table have drifted apart"
    )

    for value, code in expected.items():
        profile = resolve_course_profile(_course(value))
        assert profile.target_language == code, f"{value} resolved to {profile.target_language}"


def test_spanish_category_selects_the_spanish_voice():
    """The specific bug this replaces: a Spanish course filed under "Language"
    was narrated by the English voice."""
    assert resolve_course_profile(_course("Spanish")).tts_language == "es"


def test_python_category_enables_code_questions():
    """The other specific bug: a Python course filed under "Programming" never
    got fill-in-the-blank code exercises."""
    assert resolve_course_profile(_course("Python")).is_python is True


def test_generic_programming_is_not_treated_as_python():
    """The list must not over-claim either — a Rust course is not a Python one."""
    assert resolve_course_profile(_course("Programming")).is_python is False


def test_chess_category_allows_board_diagrams():
    assert resolve_course_profile(_course("Chess")).is_board_game is True


def test_non_board_categories_do_not_allow_board_diagrams():
    assert resolve_course_profile(_course("Philosophy")).is_board_game is False


# ---------------------------------------------------------------------------
# Keyword fallback
# ---------------------------------------------------------------------------

def test_keyword_match_is_used_when_the_model_is_unavailable():
    with patch(REQUEST_TARGET, side_effect=OSError("no ollama")):
        suggestion = suggest_category("Learn Spanish for a trip to Madrid")

    assert suggestion.value == "Spanish"
    assert suggestion.source == "keyword"


def test_keyword_match_prefers_the_more_specific_hit():
    with patch(REQUEST_TARGET, side_effect=OSError("no ollama")):
        suggestion = suggest_category("Learn Python to automate repetitive tasks at work")

    assert suggestion.value == "Python"


def test_keyword_matching_is_whole_word():
    """"html" contains "ml", which is a Data Science keyword. A substring check
    would file a web course under Data Science."""
    with patch(REQUEST_TARGET, side_effect=OSError("no ollama")):
        suggestion = suggest_category("Build a personal website with html and css")

    assert suggestion.value != "Data Science"


def test_an_unmatchable_goal_falls_back_to_general():
    with patch(REQUEST_TARGET, side_effect=OSError("no ollama")):
        suggestion = suggest_category("Something nobody has ever thought about before")

    assert suggestion.value == FALLBACK_CATEGORY
    assert suggestion.source == "default"


def test_an_empty_goal_falls_back_without_calling_the_model():
    with patch(REQUEST_TARGET, side_effect=AssertionError("model must not be called")):
        assert suggest_category("").value == FALLBACK_CATEGORY


@pytest.mark.parametrize(
    ("goal", "expected"),
    [
        ("Learn Python to automate repetitive tasks at work", "Python"),
        ("Learn Spanish to order food in Madrid", "Spanish"),
        ("Improve my chess openings and endgame technique", "Chess"),
        ("Learn to bake sourdough bread at home", "Cooking"),
        ("Get better at portrait photography", "Photography"),
        ("Understand linear algebra for graphics work", "Mathematics"),
        ("Study the history of the Roman empire", "History"),
        ("Practise guitar chords and music theory", "Music"),
    ],
)
def test_common_goals_map_to_sensible_categories(goal, expected):
    """The vocabulary is only useful if a plausible goal lands on the right
    entry without the model. This is the fallback being exercised as a
    classifier in its own right, not merely as an error path."""
    with patch(REQUEST_TARGET, side_effect=OSError("no ollama")):
        assert suggest_category(goal).value == expected


# ---------------------------------------------------------------------------
# Model answers
# ---------------------------------------------------------------------------

def test_a_model_answer_in_the_vocabulary_is_used():
    with patch(REQUEST_TARGET, return_value=_model_says("Philosophy")):
        suggestion = suggest_category("Read the Stoics properly")

    assert suggestion.value == "Philosophy"
    assert suggestion.source == "model"


def test_a_model_answer_outside_the_vocabulary_is_rejected():
    """The negative constraint. A prompt cannot promise "must not invent a
    category", so the promise is kept here instead — and the goal still gets a
    usable answer rather than a 500."""
    with patch(REQUEST_TARGET, return_value=_model_says("Underwater Basket Weaving")):
        suggestion = suggest_category("Learn to weave baskets underwater")

    assert suggestion.value == FALLBACK_CATEGORY
    assert suggestion.source == "default"


def test_an_out_of_vocabulary_answer_falls_back_to_the_keyword_match():
    with patch(REQUEST_TARGET, return_value=_model_says("Underwater Basket Weaving")):
        suggestion = suggest_category("Learn Spanish to read Borges")

    assert suggestion.value == "Spanish"
    assert suggestion.source == "keyword"


def test_surrounding_prose_does_not_break_the_parse():
    """Ollama's `format: json` is a request, not a guarantee."""
    with patch(
        REQUEST_TARGET,
        return_value='Sure! Here you go:\n```json\n{"category": "Music"}\n```',
    ):
        assert suggest_category("Learn guitar chords").value == "Music"


@pytest.mark.parametrize("answer", ['{"category": null}', "{}", '{"category": 7}'])
def test_a_malformed_category_field_is_rejected(answer):
    with patch(REQUEST_TARGET, return_value=answer):
        assert suggest_category("Learn statistics").value == "Statistics"


def test_invalid_json_falls_back_instead_of_raising():
    with patch(REQUEST_TARGET, return_value="I cannot help with that."):
        assert suggest_category("Learn Spanish").value == "Spanish"


def test_a_response_with_no_json_object_falls_back():
    with patch(REQUEST_TARGET, return_value=""):
        assert suggest_category("Learn Spanish").value == "Spanish"


# ---------------------------------------------------------------------------
# resolve_category — what actually gets stored
# ---------------------------------------------------------------------------

def test_a_known_value_is_stored_unchanged():
    with patch(REQUEST_TARGET, side_effect=AssertionError("must not call the model")):
        assert resolve_category("Programming", "Learn Rust") == "Programming"


def test_a_known_value_is_canonicalised_by_case():
    with patch(REQUEST_TARGET, side_effect=AssertionError("must not call the model")):
        assert resolve_category("python", "Learn Python") == "Python"


def test_auto_is_resolved_from_the_goal():
    with patch(REQUEST_TARGET, return_value=_model_says("Spanish")):
        assert resolve_category(AUTO, "Learn Spanish for a trip") == "Spanish"


def test_auto_falls_back_when_the_model_is_down():
    """The course must still generate. Category is cosmetic next to the plan."""
    with patch(REQUEST_TARGET, side_effect=OSError("connection refused")):
        assert resolve_category(AUTO, "Learn Spanish for a trip") == "Spanish"


def test_auto_with_no_usable_signal_stores_the_fallback():
    with patch(REQUEST_TARGET, side_effect=OSError("connection refused")):
        assert resolve_category(AUTO, "Explore something entirely unclassifiable") == (
            FALLBACK_CATEGORY
        )


def test_an_unlisted_value_from_other_is_kept():
    """"Other" exists so the list is not a cage. Overwriting what the learner
    typed with a nearest neighbour would be worse than storing it."""
    with patch(REQUEST_TARGET, side_effect=AssertionError("must not call the model")):
        assert resolve_category("Marine Biology", "Learn about coral reefs") == (
            "Marine Biology"
        )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

def test_categories_endpoint_matches_the_vocabulary(client):
    """The dropdown and the create-path validation must come from one list."""
    response = client.get("/courses/categories")
    assert response.status_code == 200

    data = response.json()
    assert [option["value"] for option in data] == [c.value for c in CATEGORIES]
    assert all(option["group"] for option in data)


def test_categories_endpoint_is_not_shadowed_by_the_course_id_route(client):
    """`/courses/categories` sits above `/courses/{course_id}`; registered the
    other way round it would be read as a course id and 404."""
    assert client.get("/courses/categories").status_code == 200


def test_suggestion_endpoint_returns_a_vocabulary_value(client):
    with patch(REQUEST_TARGET, return_value=_model_says("History")):
        response = client.post("/courses/category-suggestion", json={"goal": "Read about Rome"})

    assert response.status_code == 200
    body = response.json()
    assert body["value"] in CATEGORY_VALUES
    assert body["source"] == "model"


def test_suggestion_endpoint_rejects_a_too_short_goal(client):
    assert client.post("/courses/category-suggestion", json={"goal": "ab"}).status_code == 422


def test_suggestion_endpoint_survives_an_unreachable_model(client):
    with patch(REQUEST_TARGET, side_effect=OSError("connection refused")):
        response = client.post("/courses/category-suggestion", json={"goal": "Learn Spanish"})

    assert response.status_code == 200
    assert response.json()["value"] == "Spanish"


def test_creating_a_course_in_auto_mode_stores_a_resolved_category(client):
    llm_course = {
        "title": "Test Course",
        "description": "A description.",
        "modules": [
            {
                "title": "Module 1",
                "description": "Description.",
                "lessons": [
                    {
                        "title": "Lesson 1",
                        "description": "Two sentences. Really.",
                        "duration_minutes": 45,
                        "objectives": ["By the end, learners will be able to test."],
                    }
                ],
            }
        ],
    }

    with patch(REQUEST_TARGET, side_effect=OSError("connection refused")):
        with patch(
            "app.routes.courses.generate_course", return_value=llm_course
        ) as generate:
            response = client.post(
                "/courses",
                json={
                    "goal": "Learn Spanish to order food in Madrid",
                    "duration": "short_term",
                    "category": AUTO,
                },
            )

    assert response.status_code == 201
    # Resolved before generation, so the prompt receives a real category rather
    # than the sentinel.
    assert generate.call_args.kwargs["category"] == "Spanish"
    assert response.json()["category"] == "Spanish"


def test_creating_a_course_does_not_call_the_classifier_for_a_known_category(client):
    """An explicitly chosen category must not cost a round trip, and must not be
    silently replaced by the model's opinion."""
    with patch(
        "app.routes.courses.generate_course",
        return_value={
            "title": "T",
            "description": "D",
            "modules": [
                {
                    "title": "M",
                    "description": "D",
                    "lessons": [
                        {
                            "title": "L",
                            "description": "D",
                            "duration_minutes": 45,
                            "objectives": ["O"],
                        }
                    ],
                }
            ],
        },
    ):
        response = client.post(
            "/courses",
            json={
                "goal": "Learn Spanish to order food in Madrid",
                "duration": "short_term",
                "category": "Philosophy",
            },
        )

    assert response.json()["category"] == "Philosophy"
