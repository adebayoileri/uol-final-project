"""A closed vocabulary for `Course.category`, and a model-backed way to pick one.

`category` was a free-text box, which meant the same intent arrived as
"Programming", "python" or "Coding" and downstream features had to guess what
they had been given. Two of them guess badly, and both are silent: question style
(a Python course filed under "Programming" never got fill-in-the-blank code
exercises) and narration voice (a Spanish course filed under "Language" was read
by the English voice). `course_profile.resolve_course_profile` is the workaround
— it reads goal, category and title together precisely because category alone
could not be trusted.

This module makes category trustworthy again by offering a closed list whose
values *carry the keyword the resolver looks for*. The language categories are
derived from the resolver's own keyword table rather than restated, so the
vocabulary and the resolver cannot drift apart. "Auto" mode asks the model to
choose from that same list, which means the two routes to a category produce
values from one set — a model-detected category is not a second taxonomy.

Nothing here raises. Category is cosmetic next to generating a course, so an
unreachable model, a slow one, or one that answers with something outside the
list degrades to a deterministic keyword match and then to "General". Failing the
request would trade a whole course plan for a label.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import httpx

from app.services.course_profile import (
    BOARD_GAME_KEYWORDS,
    LANGUAGE_KEYWORDS,
    PYTHON_KEYWORDS,
)
from app.services.llm_json import extract_json_object

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
# Shorter than every other call in the codebase: this classifies one string into
# one word. It is also the only call the learner might sit through while typing,
# so the ceiling is deliberately low — a slow answer is worse than no answer,
# because no answer has a keyword fallback.
OLLAMA_TIMEOUT = float(os.environ.get("OLLAMA_CATEGORY_TIMEOUT_SECONDS", "20"))
CATEGORY_NUM_CTX = int(os.environ.get("OLLAMA_CATEGORY_NUM_CTX", "4096"))
CATEGORY_NUM_PREDICT = int(os.environ.get("OLLAMA_CATEGORY_NUM_PREDICT", "32"))

_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
_SUGGEST_TEMPLATE: str = (_PROMPTS_DIR / "category_suggestion.txt").read_text()

_SUGGEST_SYSTEM = (
    "You sort learning goals into a fixed list of categories. You reply with "
    "exactly one category name copied verbatim from the list you are given, "
    "never a new one, and you output ONLY a JSON object matching the schema in "
    "the user message — no markdown, no prose, no code fences."
)

#: Sentinel the form sends when the learner has not chosen. Also the value
#: `resolve_category` will accept as "decide for me".
AUTO = "auto"

#: Where an unclassifiable goal lands. Named rather than empty because the column
#: is displayed on course cards, and "" reads as a bug.
FALLBACK_CATEGORY = "General"


@dataclass(frozen=True)
class Category:
    """One entry in the vocabulary.

    `value` is what gets stored in `Course.category` and shown to the course
    prompt, so it is the load-bearing field — `keywords` exist to make sure the
    resolver recognises it. `note` explains a behaviour a learner would otherwise
    have no way of guessing.
    """

    value: str
    group: str
    label: str = ""
    keywords: tuple[str, ...] = field(default=())
    note: str = ""

    @property
    def display(self) -> str:
        return self.label or self.value


def _language(value: str, code: str, note: str = "") -> Category:
    """A language category whose keywords come from the resolver's table."""
    return Category(
        value=value,
        group="Languages",
        keywords=LANGUAGE_KEYWORDS[code],
        note=note,
    )


#: The vocabulary, in dropdown order. Order is deliberate: the two categories
#: whose correct spelling changes what the system generates come first in their
#: group, because "Programming" is the tempting wrong answer for both.
CATEGORIES: tuple[Category, ...] = (
    # -- Technology --------------------------------------------------------
    Category(
        value="Python",
        group="Technology",
        keywords=PYTHON_KEYWORDS,
        note="Python courses get fill-in-the-blank code questions.",
    ),
    Category(
        value="Programming",
        group="Technology",
        keywords=(
            "programming", "software", "coding", "developer", "javascript",
            "typescript", "rust", "golang", "java", "c++", "react", "sql",
            "api", "debugging", "algorithm",
        ),
    ),
    Category(
        value="Data Science",
        group="Technology",
        keywords=(
            "data science", "machine learning", "deep learning", "neural network",
            "data analysis", "analytics", "dataset", "ml", "pandas", "numpy",
        ),
    ),
    # -- Maths & Science ---------------------------------------------------
    Category(
        value="Mathematics",
        group="Maths & Science",
        keywords=(
            "mathematics", "maths", "algebra", "calculus", "geometry",
            "trigonometry", "linear algebra", "number theory",
        ),
    ),
    Category(
        value="Statistics",
        group="Maths & Science",
        keywords=(
            "statistics", "statistical", "probability", "regression",
            "hypothesis test", "distribution", "bayes",
        ),
    ),
    Category(
        value="Science",
        group="Maths & Science",
        keywords=(
            "physics", "chemistry", "biology", "science", "astronomy",
            "genetics", "neuroscience", "climate",
        ),
    ),
    # -- Languages ---------------------------------------------------------
    # Derived from the resolver's table so a stored category is always one the
    # resolver recognises. Only Spanish has a Piper voice; the rest resolve to
    # `target_language` with an English voice, which is the intended reading —
    # the lesson prose is English and quotes the target language inline.
    _language(
        "Spanish",
        "es",
        note="Spanish courses use the Spanish narration voice.",
    ),
    _language("French", "fr"),
    _language("German", "de"),
    _language("Italian", "it"),
    _language("Portuguese", "pt"),
    _language("Japanese", "ja"),
    _language("Chinese", "zh"),
    # -- Humanities --------------------------------------------------------
    Category(
        value="History",
        group="Humanities",
        keywords=("history", "historical", "ancient", "medieval", "empire", "war"),
    ),
    Category(
        value="Philosophy",
        group="Humanities",
        keywords=("philosophy", "philosophical", "ethics", "epistemology", "metaphysics"),
    ),
    Category(
        value="Literature",
        group="Humanities",
        keywords=("literature", "poetry", "creative writing", "novel", "essay"),
    ),
    # -- Skills & Business -------------------------------------------------
    Category(
        value="Business",
        group="Skills & Business",
        keywords=(
            "business", "marketing", "finance", "accounting", "economics",
            "management", "startup", "entrepreneur", "investing",
        ),
    ),
    Category(
        value="Design",
        group="Skills & Business",
        keywords=("design", "ux", "ui", "figma", "typography", "graphic"),
    ),
    Category(
        value="Music",
        group="Skills & Business",
        keywords=("music", "guitar", "piano", "chords", "sight-reading", "music theory"),
    ),
    Category(
        value="Photography",
        group="Skills & Business",
        keywords=(
            "photography", "camera", "aperture", "exposure", "lightroom",
            "depth of field", "photo editing",
        ),
    ),
    Category(
        value="Cooking",
        group="Skills & Business",
        keywords=(
            "cooking", "baking", "bread", "pastry", "recipe", "cuisine",
            "culinary", "knife skills", "fermentation",
        ),
    ),
    Category(
        value="Chess",
        group="Skills & Business",
        keywords=BOARD_GAME_KEYWORDS,
        note="Chess courses can use chessboard diagrams.",
    ),
    Category(
        value="Health & Fitness",
        group="Skills & Business",
        keywords=(
            "health", "fitness", "nutrition", "exercise", "anatomy", "yoga",
            "running", "sleep", "strength training",
        ),
    ),
    # -- Other -------------------------------------------------------------
    Category(
        value=FALLBACK_CATEGORY,
        group="Other",
        note="Used when nothing else is a clear match.",
    ),
)

CATEGORY_VALUES: frozenset[str] = frozenset(c.value for c in CATEGORIES)
_BY_VALUE: dict[str, Category] = {c.value: c for c in CATEGORIES}

#: Captured once at import. Values only — the `note` on each entry describes what
#: the system does with the category, which is not the model's business and would
#: only give it something to reason about besides the goal.
_TAXONOMY_BLOCK = "\n".join(f"- {c.value}" for c in CATEGORIES)


def get_category(value: str) -> Category | None:
    """Look up a vocabulary entry, case-insensitively. None when unlisted."""
    if not value:
        return None
    return _BY_VALUE.get(value.strip()) or next(
        (c for c in CATEGORIES if c.value.lower() == value.strip().lower()), None
    )


def _mentions(text: str, keyword: str) -> bool:
    """Whole-word match, case-insensitive. Keywords are always literal text.

    Substring matching is what makes a plain `in` check wrong here: "ml" is a
    keyword and "html" contains it. The lookarounds are the only mechanism —
    there is deliberately no way for a keyword to opt into being a regex, because
    a table where some entries are patterns and some are words is a table nobody
    can read correctly.
    """
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text, re.IGNORECASE) is not None


def _keyword_match(goal: str) -> Category | None:
    """The best keyword match, or None.

    Scored by number of distinct keywords hit rather than by first match: "learn
    statistics for data science" hits both, and the honest answer is the one the
    goal spends more words on. Ties go to the longer keyword, which prefers the
    specific over the general ("machine learning" over "programming").
    """
    best: Category | None = None
    best_score: tuple[int, int] = (0, 0)

    for category in CATEGORIES:
        hits = [kw for kw in category.keywords if _mentions(goal, kw)]
        if not hits:
            continue
        score = (len(hits), max(len(kw) for kw in hits))
        if score > best_score:
            best, best_score = category, score

    return best


def _match_value(text: str) -> str | None:
    """Accept a model's answer only if it is in the vocabulary.

    This is the validation layer rather than a prompt instruction, because the
    promise being made is negative — "must not be a category I made up" — and a
    prompt cannot promise a negative. An answer outside the list is discarded and
    the caller falls back, which is why the fallback exists at all.
    """
    match = get_category(text)
    return match.value if match else None


def _request_model(goal: str) -> str:
    """The raw transport call. Separated from `_ask_model` so tests can exercise
    the validation and fallback paths — the interesting ones — without standing
    up an HTTP stub."""
    prompt = _SUGGEST_TEMPLATE.format(goal=goal, taxonomy=_TAXONOMY_BLOCK)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": f"{_SUGGEST_SYSTEM}\n\n{prompt}",
        "format": "json",
        "stream": False,
        "options": {
            "num_ctx": CATEGORY_NUM_CTX,
            "num_predict": CATEGORY_NUM_PREDICT,
            # Zero, unlike every other generator here. There is no phrasing to
            # get right and exactly one correct answer, so sampling can only
            # introduce a wrong one.
            "temperature": 0.0,
        },
    }

    with httpx.Client(timeout=OLLAMA_TIMEOUT) as client:
        response = client.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload)
        response.raise_for_status()
    return response.json()["response"]


def _ask_model(goal: str) -> str | None:
    """Ask the model for one category from the list. None on any failure.

    The except clause is wider than elsewhere in the codebase on purpose. Every
    other generator failing means a lesson or a diagram has to be regenerated;
    this one failing means a label is chosen by the fallback, which is a better
    outcome than an error page. `OSError` is included because the transport can
    fail below httpx — a socket or DNS error never becomes an `httpx.HTTPError`.
    """
    try:
        parsed = extract_json_object(_request_model(goal))
    except (httpx.HTTPError, OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("Category suggestion unavailable (%s) — using keyword match.", exc)
        return None

    if not isinstance(parsed, dict):
        logger.warning("Category suggestion returned %s, not an object.", type(parsed).__name__)
        return None

    answer = parsed.get("category")
    if not isinstance(answer, str):
        logger.warning("Category suggestion returned no 'category' string: %r", parsed)
        return None

    value = _match_value(answer)
    if value is None:
        logger.warning("Category suggestion invented %r — not in the vocabulary.", answer)
    return value


@dataclass(frozen=True)
class CategorySuggestion:
    """A proposed category and where it came from.

    `source` is surfaced not as diagnostics but because it changes what the
    learner should do about it: a "keyword" or "default" answer is worth
    overriding by hand, a "model" answer usually is not.
    """

    value: str
    group: str
    label: str
    note: str
    source: Literal["model", "keyword", "default"]

    @property
    def is_guess(self) -> bool:
        return self.source != "model"


def _suggestion(category: Category, source: Literal["model", "keyword", "default"]):
    return CategorySuggestion(
        value=category.value,
        group=category.group,
        label=category.display,
        note=category.note,
        source=source,
    )


def suggest_category(goal: str) -> CategorySuggestion:
    """Pick a category for a goal. Never raises, never blocks, never empty."""
    goal = (goal or "").strip()

    if goal:
        value = _ask_model(goal)
        if value is not None:
            category = _BY_VALUE[value]
            logger.info("Category %r suggested by model.", value)
            return _suggestion(category, "model")

        # The keyword matcher is not a lesser version of the model call: it is
        # the same judgement the rest of the system already makes about a course,
        # and for an unambiguous goal ("learn Spanish") it is the better one.
        matched = _keyword_match(goal)
        if matched is not None:
            return _suggestion(matched, "keyword")

    return _suggestion(_BY_VALUE[FALLBACK_CATEGORY], "default")


def resolve_category(submitted: str, goal: str) -> str:
    """Turn whatever the client sent into the value that gets stored.

    Three cases, and the third is why this is not just a lookup:

    - a value from the vocabulary is used as-is;
    - the `AUTO` sentinel (or an empty string) means the learner asked us to
      decide, so we do — this is the path that makes the feature work when the
      preview never arrived;
    - anything else is kept. It came from "Other", where the learner typed
      something the list cannot express, and overwriting their words with a
      nearest neighbour would be worse than storing a value the resolver has to
      read the goal to interpret. That path is the old behaviour, unchanged.
    """
    known = get_category(submitted)
    if known is not None:
        return known.value

    if not submitted or submitted.strip().lower() == AUTO:
        resolved = suggest_category(goal).value
        logger.info("Category resolved automatically to %r.", resolved)
        return resolved

    return submitted.strip()
