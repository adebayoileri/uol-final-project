"""Streak and study time calculations from behavioural event data."""

from datetime import datetime, date, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.events import LESSON_COMPLETED, REVIEW_GRADED


def current_streak(db: Session) -> int:
    """Count consecutive calendar days (UTC) with ≥1 qualifying event, going back from today."""
    rows = db.execute(
        text("""
            SELECT DATE(occurred_at) as day
            FROM user_events
            WHERE event_type IN (:lc, :rg)
            GROUP BY DATE(occurred_at)
            ORDER BY day DESC
        """),
        {"lc": LESSON_COMPLETED, "rg": REVIEW_GRADED},
    ).fetchall()

    if not rows:
        return 0

    activity_days = {date.fromisoformat(r.day) for r in rows}
    today = datetime.now(timezone.utc).date()

    streak = 0
    check = today
    while check in activity_days:
        streak += 1
        check -= timedelta(days=1)

    return streak


def total_study_time_minutes(db: Session) -> float:
    """Sum of (last_activity_at - started_at) across all study sessions, in minutes."""
    rows = db.execute(
        text("SELECT started_at, last_activity_at FROM study_sessions")
    ).fetchall()

    total_seconds = 0.0
    for r in rows:
        try:
            start = datetime.fromisoformat(str(r.started_at).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(r.last_activity_at).replace("Z", "+00:00"))
            total_seconds += (end - start).total_seconds()
        except (ValueError, TypeError):
            pass

    return round(total_seconds / 60, 1)
