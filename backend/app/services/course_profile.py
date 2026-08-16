"""Resolve what kind of course this is, from what the learner actually typed.

`Course.category` is free text collected from a plain input box, so branching on
it alone is unreliable: a Spanish course was filed under "Language" and a Python
course under "Programming", which silently broke narration voice selection and
fill-in-the-blank question generation respectively.

This resolver reads goal, category and title together, which is where the signal
actually lives. It is a pure function of three columns the user already supplied,
so nothing is stored — a column would add a migration and a staleness risk for no
benefit.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.models import Course

# ISO code → the words a learner is likely to use for that language.
_LANGUAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "es": ("spanish", "español", "espanol", "castellano"),
    "fr": ("french", "français", "francais"),
    "de": ("german", "deutsch"),
    "it": ("italian", "italiano"),
    "pt": ("portuguese", "português", "portugues"),
    "ja": ("japanese", "nihongo"),
    "zh": ("chinese", "mandarin", "cantonese"),
}

# Voices actually installed for Piper (see app/services/tts.py).
_TTS_VOICES: tuple[str, ...] = ("en", "es")

_PYTHON_KEYWORDS: tuple[str, ...] = ("python", "django", "flask", "pandas", "numpy")


@dataclass(frozen=True)
class CourseProfile:
    """What downstream features need to know about a course."""

    #: ISO code of the language being learned, or None if this isn't a language course.
    target_language: str | None
    #: The voice to synthesise with. Only what Piper can actually speak.
    tts_language: Literal["en", "es"]
    #: True when code exercises should be Python specifically.
    is_python: bool

    @property
    def is_language_course(self) -> bool:
        return self.target_language is not None


def _haystack(course: "Course") -> str:
    parts = (
        getattr(course, "goal", "") or "",
        getattr(course, "category", "") or "",
        getattr(course, "title", "") or "",
    )
    return " ".join(parts).lower()


def resolve_course_profile(course: "Course") -> CourseProfile:
    """Classify a course. Never raises, including on a detached/partial object."""
    try:
        text = _haystack(course)
    except AttributeError:
        text = ""

    target_language: str | None = None
    for code, keywords in _LANGUAGE_KEYWORDS.items():
        if any(word in text for word in keywords):
            target_language = code
            break

    # Piper has voices for en and es only. Anything else falls back to English,
    # which is also the correct reading: enrichment writes definitions in English
    # and quotes the target-language material inline.
    tts_language: Literal["en", "es"] = (
        "es" if target_language == "es" else "en"
    )

    return CourseProfile(
        target_language=target_language,
        tts_language=tts_language,
        is_python=any(word in text for word in _PYTHON_KEYWORDS),
    )


def profile_for_lesson(lesson) -> CourseProfile:
    """Resolve via lesson → module → course, tolerating a partially loaded graph."""
    try:
        return resolve_course_profile(lesson.module.course)
    except AttributeError:
        return CourseProfile(target_language=None, tts_language="en", is_python=False)


def supported_tts_languages() -> tuple[str, ...]:
    return _TTS_VOICES
