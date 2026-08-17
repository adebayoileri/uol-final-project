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


def record_event(
    db: Session,
    event_type: str,
    metadata: dict | None = None,
    *,
    user_id: str,
) -> None:
    """Insert an event row and extend/create the caller's study session.

    `user_id` is keyword-only with no default on purpose. Every call site
    passes `metadata` positionally, so a third positional parameter would
    silently bind a dict to the owner — and this function swallows every
    exception, so that corruption would be invisible. Keyword-only turns a
    missed call site into a loud TypeError instead.

    Best-effort: any DB error (e.g. table not yet migrated in tests) is logged
    and swallowed so the calling route handler is never affected.
    """
    try:
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        db.execute(
            text("""
                INSERT INTO user_events (id, user_id, event_type, occurred_at, metadata)
                VALUES (:id, :uid, :type, :now, :meta)
            """),
            {
                "id": event_id,
                "uid": user_id,
                "type": event_type,
                "now": now,
                "meta": json.dumps(metadata or {}),
            },
        )

        # Upsert THIS USER's study session. Scoping the SELECT is the load-bearing
        # part: without it, two users active within the window merge into one row.
        cutoff = now - timedelta(minutes=_SESSION_GAP_MINUTES)
        row = db.execute(
            text("""
                SELECT id FROM study_sessions
                WHERE user_id = :uid AND last_activity_at >= :cutoff
                ORDER BY last_activity_at DESC LIMIT 1
            """),
            {"uid": user_id, "cutoff": cutoff},
        ).fetchone()

        if row:
            db.execute(
                text("""
                    UPDATE study_sessions
                    SET last_activity_at = :now, event_count = event_count + 1
                    WHERE id = :id AND user_id = :uid
                """),
                {"now": now, "id": row.id, "uid": user_id},
            )
        else:
            db.execute(
                text("""
                    INSERT INTO study_sessions (id, user_id, started_at, last_activity_at, event_count)
                    VALUES (:id, :uid, :now, :now, 1)
                """),
                {"id": str(uuid.uuid4()), "uid": user_id, "now": now},
            )

        db.commit()
    except Exception as exc:
        logger.warning("record_event failed (non-fatal): %s", exc)
        db.rollback()
