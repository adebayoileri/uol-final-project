"""AI learning insights: optimal study time, recommended focus, next due cards."""

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.events import QUESTION_ANSWERED
from app.services.mastery import card_mastery

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")


def optimal_study_time(db: Session, user_id: str) -> dict | None:
    """Return the 2-hour window with the highest average answer score.

    Requires ≥20 QUESTION_ANSWERED events. Returns None if insufficient data.
    """
    rows = db.execute(
        text("""
            SELECT occurred_at, json_extract(metadata, '$.score') as score
            FROM user_events
            WHERE event_type = :et
              AND user_id = :uid
              AND json_extract(metadata, '$.score') IS NOT NULL
        """),
        {"et": QUESTION_ANSWERED, "uid": user_id},
    ).fetchall()

    if len(rows) < 20:
        return None

    hour_scores: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        try:
            dt = datetime.fromisoformat(str(row.occurred_at).replace("Z", "+00:00"))
            hour = dt.hour
            score = float(row.score)
            hour_scores[hour].append(score)
        except (ValueError, TypeError):
            continue

    if not hour_scores:
        return None

    # Find 2-hour window with highest average score
    best_start = 0
    best_score = -1.0
    for start_hour in range(24):
        window_hours = [start_hour, (start_hour + 1) % 24]
        scores = []
        for h in window_hours:
            scores.extend(hour_scores.get(h, []))
        if len(scores) >= 3:
            avg = sum(scores) / len(scores)
            if avg > best_score:
                best_score = avg
                best_start = start_hour

    if best_score < 0:
        return None

    return {
        "start_hour": best_start,
        "end_hour": (best_start + 2) % 24,
    }


def _ollama_rationale(concept: str) -> str:
    """Generate a one-sentence rationale for why a concept needs attention."""
    prompt = (
        f"In one sentence, explain why a student might struggle with this concept: '{concept}'. "
        "Be specific and constructive. Start with 'This concept'."
    )
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
            res.raise_for_status()
            return res.json()["response"].strip()
    except Exception as exc:
        logger.warning("Could not generate rationale: %s", exc)
        return "This concept has the lowest mastery score and would benefit from focused review."


def recommended_focus(course_id: str, db: Session) -> dict | None:
    """Return the lowest-mastery card with an AI-generated rationale."""
    rows = db.execute(
        text("""
            SELECT q.text as question_text, c.stability
            FROM cards c
            JOIN questions q ON q.id = c.question_id
            WHERE c.course_id = :course_id
        """),
        {"course_id": course_id},
    ).fetchall()

    if not rows:
        return None

    # Find lowest mastery card
    lowest = min(rows, key=lambda r: card_mastery(r.stability))
    concept = lowest.question_text[:80].strip()
    rationale = _ollama_rationale(concept)

    return {
        "concept": concept,
        "mastery": round(card_mastery(lowest.stability), 3),
        "rationale": rationale,
    }


def next_reviews(course_id: str, db: Session, n: int = 3) -> list[dict[str, Any]]:
    """Return the next N cards due for review in a course."""
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = db.execute(
        text("""
            SELECT q.text as question_text, c.due
            FROM cards c
            JOIN questions q ON q.id = c.question_id
            WHERE c.course_id = :course_id AND c.due > :now
            ORDER BY c.due ASC
            LIMIT :n
        """),
        {"course_id": course_id, "now": now_iso, "n": n},
    ).fetchall()

    return [
        {"question_text": r.question_text[:80], "due": r.due}
        for r in rows
    ]
