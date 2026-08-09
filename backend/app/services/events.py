"""Behavioural event recording and study session tracking."""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Event type constants
LESSON_STARTED = "lesson_started"
LESSON_COMPLETED = "lesson_completed"
QUESTION_ANSWERED = "question_answered"
REVIEW_GRADED = "review_graded"
COURSE_GENERATED = "course_generated"

_SESSION_GAP_MINUTES = 10


def record_event(db: Session, event_type: str, metadata: dict | None = None) -> None:
    """Insert an event row and extend/create the current study session.

    Best-effort: any DB error (e.g. table not yet migrated in tests) is logged
    and swallowed so the calling route handler is never affected.
    """
    try:
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        db.execute(
            text("""
                INSERT INTO user_events (id, event_type, occurred_at, metadata)
                VALUES (:id, :type, :now, :meta)
            """),
            {"id": event_id, "type": event_type, "now": now, "meta": json.dumps(metadata or {})},
        )

        # Upsert study session: extend if last activity < 10 min ago, else create new
        cutoff = now - timedelta(minutes=_SESSION_GAP_MINUTES)
        row = db.execute(
            text("SELECT id FROM study_sessions WHERE last_activity_at >= :cutoff ORDER BY last_activity_at DESC LIMIT 1"),
            {"cutoff": cutoff},
        ).fetchone()

        if row:
            db.execute(
                text("UPDATE study_sessions SET last_activity_at = :now, event_count = event_count + 1 WHERE id = :id"),
                {"now": now, "id": row.id},
            )
        else:
            db.execute(
                text("""
                    INSERT INTO study_sessions (id, started_at, last_activity_at, event_count)
                    VALUES (:id, :now, :now, 1)
                """),
                {"id": str(uuid.uuid4()), "now": now},
            )

        db.commit()
    except Exception as exc:
        logger.warning("record_event failed (non-fatal): %s", exc)
        db.rollback()
