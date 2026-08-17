"""Practice drill endpoints.

GET  /courses/{id}/drills             — what this course can offer, and why not
GET  /courses/{id}/drills/{kind}      — the items
POST /courses/{id}/drills/{kind}/complete — record a finished drill
"""

import hashlib
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_course
from app.database import get_db
from app.models import Course, User
from app.services.course_profile import resolve_course_profile
from app.services.drills import (
    DRILL_KINDS,
    build_drill,
    drill_availability,
    load_course_lessons,
)
from app.services.events import record_event
from app.achievements.engine import evaluate_achievements
from app.services.tts import synthesize_speech

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["drills"])

DRILL_COMPLETED = "drill_completed"

# Reuses the narration directory and its /audio/{filename} server.
_AUDIO_DIR = Path(__file__).parent.parent.parent / "data" / "narration"
_AUDIO_DIR.mkdir(parents=True, exist_ok=True)


def _get_course(course_id: str, db: Session, user_id: str) -> Course:
    return get_owned_course(db, course_id, user_id)


@router.get("/{course_id}/drills")
def list_drills(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    course = _get_course(course_id, db, user.id)
    return drill_availability(course, load_course_lessons(course_id, db))


def _synthesise_cached(text: str, lang: str) -> str | None:
    """Render `text` to a cached WAV and return its public URL, or None."""
    digest = hashlib.sha256(f"{lang}:{text}".encode()).hexdigest()[:16]
    filename = f"drill_{digest}.wav"
    path = _AUDIO_DIR / filename
    if not path.is_file():
        try:
            path.write_bytes(synthesize_speech(text, lang=lang))  # type: ignore[arg-type]
        except RuntimeError as exc:
            # A missing Piper voice must degrade the drill, not 500 the request.
            logger.warning("Drill audio synthesis failed: %s", exc)
            return None
    return f"/audio/{filename}"


@router.get("/{course_id}/drills/{kind}")
def get_drill(
    course_id: str,
    kind: str,
    n: int = Query(default=8, ge=1, le=30),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if kind not in DRILL_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown drill '{kind}'.")

    course = _get_course(course_id, db, user.id)
    lessons = load_course_lessons(course_id, db)
    items = build_drill(kind, course, lessons, n)  # type: ignore[arg-type]

    if not items:
        availability = drill_availability(course, lessons)
        reason = next(
            (d["reason"] for d in availability["drills"] if d["kind"] == kind),
            "Not enough content yet",
        )
        raise HTTPException(status_code=409, detail=reason or "Not enough content yet")

    if kind == "listen":
        lang = resolve_course_profile(course).tts_language
        playable = []
        for item in items:
            url = _synthesise_cached(item["speak"], lang)
            if url is None:
                continue
            # The spoken text never reaches the client — being able to read it
            # would defeat a listening drill.
            item.pop("speak", None)
            item["audio_url"] = url
            playable.append(item)
        if not playable:
            raise HTTPException(
                status_code=503,
                detail="Audio is unavailable — check the Piper voice is installed.",
            )
        items = playable

    return {"kind": kind, "course_id": course_id, "course_title": course.title, "items": items}


@router.post("/{course_id}/drills/{kind}/complete", status_code=204)
def complete_drill(
    course_id: str,
    kind: str,
    correct: int = Query(default=0, ge=0),
    total: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Record a finished drill.

    Drills feed streaks and achievements but deliberately do NOT touch FSRS:
    practice is not scheduled review, and folding it into the scheduler would
    corrupt the stability estimates the review system depends on.
    """
    if kind not in DRILL_KINDS:
        raise HTTPException(status_code=404, detail=f"Unknown drill '{kind}'.")
    _get_course(course_id, db, user.id)

    record_event(
        db,
        DRILL_COMPLETED,
        {"course_id": course_id, "kind": kind, "correct": correct, "total": total},
        user_id=user.id,
    )
    evaluate_achievements(db, user_id=user.id)
    return None
