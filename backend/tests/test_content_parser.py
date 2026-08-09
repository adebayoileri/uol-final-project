"""Tests for app.services.content_parser.parse_lesson_body."""

import json
import pytest
from app.services.content_parser import parse_lesson_body


FULL_LESSON = {
    "title": "Variables and Data Types",
    "description": "Covers Python's built-in types.",
    "duration_minutes": 45,
    "objectives": ["By the end, identify all primitive types."],
    "key_concepts": [
        {"name": "int", "definition": "Whole numbers.", "example": "x = 42"},
        {"name": "str", "definition": "Text sequences.", "example": 'name = "Alice"'},
    ],
    "worked_example": "Step 1: declare x = 10\nStep 2: print(type(x))",
    "common_pitfalls": ["Confusing int and float.", "String concatenation with non-strings."],
    "practice_prompts": ["Create a variable for each type.", "Demonstrate type coercion."],
}


def test_full_structured_input():
    raw = json.dumps(FULL_LESSON)
    result = parse_lesson_body(raw)

    assert result["is_structured"] is True
    assert len(result["key_concepts"]) == 2
    assert result["key_concepts"][0]["name"] == "int"
    assert result["key_concepts"][1]["example"] == 'name = "Alice"'
    assert result["worked_example"] == "Step 1: declare x = 10\nStep 2: print(type(x))"
    assert len(result["common_pitfalls"]) == 2
    assert len(result["practice_prompts"]) == 2


def test_missing_common_pitfalls():
    data = {**FULL_LESSON}
    del data["common_pitfalls"]
    result = parse_lesson_body(json.dumps(data))

    assert result["is_structured"] is True
    assert result["common_pitfalls"] == []
    # Other fields still present
    assert len(result["key_concepts"]) == 2
    assert result["worked_example"] is not None


def test_missing_worked_example():
    data = {**FULL_LESSON}
    del data["worked_example"]
    result = parse_lesson_body(json.dumps(data))

    assert result["worked_example"] is None
    assert result["is_structured"] is True


def test_malformed_json():
    result = parse_lesson_body("{not valid json: [}")

    assert result["is_structured"] is False
    assert result["key_concepts"] == []
    assert result["worked_example"] is None
    assert result["common_pitfalls"] == []
    assert result["practice_prompts"] == []


def test_plain_text_description():
    result = parse_lesson_body("This lesson covers the basics of Python variables.")

    assert result["is_structured"] is False
    assert result["key_concepts"] == []
    assert result["worked_example"] is None


def test_empty_string():
    result = parse_lesson_body("")

    assert result["is_structured"] is False
    assert result["key_concepts"] == []


def test_key_concepts_with_missing_name_filtered():
    data = {
        **FULL_LESSON,
        "key_concepts": [
            {"name": "int", "definition": "Whole numbers.", "example": "x = 1"},
            {"definition": "No name here.", "example": "..."},  # missing name
            {"name": "", "definition": "Empty name.", "example": "..."},  # empty name
        ],
    }
    result = parse_lesson_body(json.dumps(data))

    # Only the first concept has a non-empty name
    assert len(result["key_concepts"]) == 1
    assert result["key_concepts"][0]["name"] == "int"


def test_key_concepts_wrong_type_is_ignored():
    data = {**FULL_LESSON, "key_concepts": "should be a list"}
    result = parse_lesson_body(json.dumps(data))

    assert result["is_structured"] is True
    assert result["key_concepts"] == []


def test_practice_prompts_strips_whitespace():
    data = {**FULL_LESSON, "practice_prompts": ["  write a loop  ", "  use a dict  "]}
    result = parse_lesson_body(json.dumps(data))

    assert result["practice_prompts"] == ["write a loop", "use a dict"]
