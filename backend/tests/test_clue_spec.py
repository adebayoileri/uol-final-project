"""Tests for listening-clue validation.

The leak detector is the point of this module, so most of these are a table over
the ways a term can be named without being spelled exactly. Each case is a way
the audio could hand over its answer while looking, to a prompt review, as
though it had not.
"""

import json

import pytest

from app.clue_spec import (
    MAX_CLUE_CHARS,
    MAX_CLUES_PER_LESSON,
    MIN_CLUE_CHARS,
    mentioned_name,
    validate_clues,
)
from app.models import Lesson

GOOD = "A value that has to be crossed before the model commits to one category rather than the other."


# ---------------------------------------------------------------------------
# The leak detector
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "clue,name",
    [
        # The plain case: the term is right there.
        ("Overfitting happens when a model memorises its training set.", "Overfitting"),
        ("overfitting happens when a model memorises its training set.", "Overfitting"),
        # Case and punctuation are form, not identity.
        ("This is what people mean by OVERFITTING.", "Overfitting"),
        ("A case of over-fitting, where noise is memorised.", "Overfitting"),
        # Inflections of the same word.
        ("The model has overfit its training data.", "Overfitting"),
        ("Two overfitted models compared.", "Overfitting"),
        # A multi-word term spelled with a hyphen instead of a space.
        ("This is what gradient-descent does to the weights.", "Gradient Descent"),
        ("It is a step of gradient descent toward a minimum.", "Gradient Descent"),
        # The head noun alone still names half the answer.
        ("The threshold is the point where the decision flips.", "Classification Threshold"),
        ("Reading the matrix tells you where the errors sit.", "Confusion Matrix"),
        # The acronym counts as naming it.
        ("An SVM finds the widest separating boundary.", "Support Vector Machine"),
    ],
)
def test_a_named_term_is_detected(clue, name):
    assert mentioned_name(clue, name) is not None


@pytest.mark.parametrize(
    "clue,name",
    [
        # The intended shape: mechanism, no term.
        ("A model that has memorised its training data, including its noise, so it "
         "scores well on what it has seen and poorly on anything new.", "Overfitting"),
        # Shares a prefix with a name token but is a different word.
        ("Ratings are averaged across the fold.", "Learning Rate"),
        # Short fragments must not trip the fuzzy comparison.
        ("The data is split into two halves.", "Dataset"),
        ("A category the model chooses at the end.", "Class"),
    ],
)
def test_a_clue_that_does_not_name_its_term_passes(clue, name):
    assert mentioned_name(clue, name) is None


def test_a_name_with_no_alphanumeric_characters_is_never_a_leak():
    """A name that normalises to nothing cannot be matched, and must not crash."""
    assert mentioned_name("Anything at all.", "!!!") is None


# ---------------------------------------------------------------------------
# validate_clues
# ---------------------------------------------------------------------------

def test_valid_clues_are_kept_and_keyed_by_the_lessons_spelling():
    """The model's casing is discarded: the drill looks the key up casefolded,
    so storing its spelling instead of the lesson's would be a lookup that
    silently misses."""
    kept = validate_clues(
        {"clues": [{"name": "OVERFITTING", "clue": GOOD}]},
        ["Overfitting"],
    )
    assert list(kept) == ["Overfitting"]
    assert kept["Overfitting"] == GOOD


def test_the_mapping_form_is_accepted_too():
    kept = validate_clues({"clues": {"Overfitting": GOOD}}, ["Overfitting"])
    assert kept == {"Overfitting": GOOD}


def test_a_leaky_clue_is_dropped_without_discarding_the_good_ones():
    """One bad clue must not cost the lesson its other clues — the same
    per-item independence validate_diagrams gives each diagram."""
    kept = validate_clues(
        {
            "clues": [
                {"name": "Overfitting", "clue": "Overfitting is when noise is memorised."},
                {"name": "Threshold", "clue": GOOD},
            ]
        },
        ["Overfitting", "Threshold"],
    )
    assert list(kept) == ["Threshold"]


def test_a_clue_for_a_concept_this_lesson_does_not_have_is_dropped():
    kept = validate_clues(
        {"clues": [
            {"name": "Invented Term", "clue": GOOD},
            {"name": "Overfitting", "clue": GOOD},
        ]},
        ["Overfitting"],
    )
    assert list(kept) == ["Overfitting"]


@pytest.mark.parametrize("clue", ["Too short.", " " * MIN_CLUE_CHARS, ""])
def test_clues_below_the_floor_are_dropped(clue):
    with pytest.raises(ValueError):
        validate_clues({"clues": [{"name": "Overfitting", "clue": clue}]}, ["Overfitting"])


def test_a_clue_above_the_ceiling_is_dropped():
    with pytest.raises(ValueError):
        validate_clues(
            {"clues": [{"name": "Overfitting", "clue": "x" * (MAX_CLUE_CHARS + 1)}]},
            ["Overfitting"],
        )


def test_entries_missing_a_name_or_a_clue_are_dropped():
    with pytest.raises(ValueError):
        validate_clues(
            {"clues": [{"name": "Overfitting"}, {"clue": GOOD}]},
            ["Overfitting"],
        )


def test_the_lesson_concept_count_is_not_a_cap_but_a_runaway_response_is():
    names = [f"Concept {i}" for i in range(MAX_CLUES_PER_LESSON + 4)]
    kept = validate_clues(
        {"clues": [{"name": n, "clue": GOOD} for n in names]},
        names,
    )
    assert len(kept) == MAX_CLUES_PER_LESSON


def test_every_entry_leaking_raises_so_the_caller_retries():
    with pytest.raises(ValueError):
        validate_clues(
            {"clues": [{"name": "Overfitting", "clue": "This is overfitting, plainly."}]},
            ["Overfitting"],
        )


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"clues": None},
        {"clues": []},
        {"clues": {}},
        {"clues": "not a container"},
        {"clues": 7},
    ],
)
def test_an_unusable_response_raises_rather_than_storing_an_empty_map(payload):
    """Unlike diagrams there is no legitimate 'none apply' answer: every concept
    is describable, so an empty result means the drill cannot run and must be
    retried rather than cached as an empty clue set."""
    with pytest.raises(ValueError):
        validate_clues(payload, ["Overfitting"])


def test_a_non_dict_payload_raises():
    with pytest.raises(ValueError):
        validate_clues(["clues"], ["Overfitting"])


# ---------------------------------------------------------------------------
# The storage contract
# ---------------------------------------------------------------------------

def test_validated_clues_round_trip_through_the_lesson_property():
    """`validate_clues` writes what `Lesson.clues` reads; this pins that pair
    together so a change to either shape is caught here."""
    kept = validate_clues({"clues": {"Overfitting": GOOD}}, ["Overfitting"])

    lesson = Lesson()
    lesson.clues_json = json.dumps({"clues": kept})

    assert lesson.clues == {"overfitting": GOOD}


def test_the_property_is_none_before_generation_and_empty_when_unreadable():
    lesson = Lesson()
    assert lesson.clues is None

    lesson.clues_json = "not json"
    assert lesson.clues == {}

    lesson.clues_json = json.dumps(["wrong shape"])
    assert lesson.clues == {}


def test_blank_entries_are_not_returned_by_the_property():
    lesson = Lesson()
    lesson.clues_json = json.dumps({"clues": {"Overfitting": "   ", "": GOOD}})
    assert lesson.clues == {}
