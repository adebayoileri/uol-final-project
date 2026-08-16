"""Regression tests for course classification.

The two cases marked LIVE BUG below were both broken in production against the
real database: branching on `Course.category` alone missed a Spanish course
filed under "Language" and a Python course filed under "Programming".
"""

import pytest

from app.models import Course
from app.services.course_profile import profile_for_lesson, resolve_course_profile


def _course(goal: str, category: str, title: str) -> Course:
    return Course(
        goal=goal,
        duration="short_term",
        category=category,
        title=title,
        description="A course.",
    )


# ---------------------------------------------------------------------------
# The two live bugs
# ---------------------------------------------------------------------------

def test_spanish_course_filed_under_language_resolves_to_spanish():
    """LIVE BUG: category was 'Language', so the ES voice was never selected."""
    profile = resolve_course_profile(
        _course("Learn conversational Spanish basics", "Language", "Spanish for Beginners")
    )
    assert profile.target_language == "es"
    assert profile.tts_language == "es"
    assert profile.is_language_course is True


def test_python_course_filed_under_programming_is_python():
    """LIVE BUG: category was 'Programming', so code exercises never generated."""
    profile = resolve_course_profile(
        _course("Learn Python file I/O for automation", "Programming", "Python File I/O Basics")
    )
    assert profile.is_python is True


# ---------------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "goal,expected",
    [
        ("Learn French for travel", "fr"),
        ("Get conversational in German", "de"),
        ("Study Italian cooking vocabulary", "it"),
        ("Learn Portuguese basics", "pt"),
        ("Learn Japanese writing", "ja"),
    ],
)
def test_detects_other_languages(goal, expected):
    assert resolve_course_profile(_course(goal, "Language", "A course")).target_language == expected


def test_unsupported_voice_falls_back_to_english_without_crashing():
    """Piper has no French voice; a French course must degrade, not fail."""
    profile = resolve_course_profile(_course("Learn French", "Language", "French 101"))
    assert profile.target_language == "fr"
    assert profile.tts_language == "en"


def test_accented_spelling_is_detected():
    assert resolve_course_profile(_course("Aprender español", "Idiomas", "Curso")).target_language == "es"


@pytest.mark.parametrize(
    "goal,category,title",
    [
        ("Understand core ML concepts", "Data Science", "Machine Learning Concepts"),
        ("How to play chess", "Games", "Learning Chess Fundamentals"),
        ("Understanding history of AI and ML", "Artificial Intelligence", "History of AI"),
    ],
)
def test_non_language_courses_have_no_target_language(goal, category, title):
    profile = resolve_course_profile(_course(goal, category, title))
    assert profile.target_language is None
    assert profile.is_language_course is False
    assert profile.tts_language == "en"


# ---------------------------------------------------------------------------
# Python detection
# ---------------------------------------------------------------------------

def test_python_detected_from_title_alone():
    assert resolve_course_profile(_course("Automate my job", "Tech", "Python Scripting")).is_python


def test_non_python_programming_course_is_not_python():
    """A JavaScript course must not receive Python fill-in-the-blank exercises."""
    profile = resolve_course_profile(
        _course("Learn JavaScript for the web", "Programming", "Modern JavaScript")
    )
    assert profile.is_python is False


def test_chess_course_is_not_python():
    assert not resolve_course_profile(_course("How to play chess", "Games", "Chess")).is_python


# ---------------------------------------------------------------------------
# Robustness
# ---------------------------------------------------------------------------

def test_resolver_tolerates_missing_fields():
    class Bare:
        pass

    profile = resolve_course_profile(Bare())
    assert profile.target_language is None
    assert profile.tts_language == "en"
    assert profile.is_python is False


def test_profile_for_lesson_tolerates_detached_graph():
    class Detached:
        module = None

    profile = profile_for_lesson(Detached())
    assert profile.target_language is None
    assert profile.tts_language == "en"


def test_profile_for_lesson_walks_the_relationship():
    from app.models import Lesson, Module

    course = _course("Learn conversational Spanish", "Language", "Spanish")
    module = Module(course=course, order_index=0, title="M", description="d")
    lesson = Lesson(module=module, order_index=0, title="L", description="d", duration_minutes=10)

    assert profile_for_lesson(lesson).tts_language == "es"
