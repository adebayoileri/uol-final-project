"""Achievement evaluation engine."""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.achievements.catalogue import CATALOGUE

logger = logging.getLogger(__name__)


def evaluate_achievements(db: Session) -> list[str]:
    """Check all achievements and unlock any newly earned ones.

    Returns list of achievement IDs newly unlocked this call. Best-effort:
    any DB error is logged and swallowed so routes are never blocked.
    """
    try:
        already_unlocked = {
            row.achievement_id
            for row in db.execute(text("SELECT achievement_id FROM user_achievements")).fetchall()
        }
    except Exception as exc:
        logger.warning("evaluate_achievements: could not read achievements: %s", exc)
        return []

    newly_unlocked: list[str] = []
    for achievement in CATALOGUE:
        if achievement.id in already_unlocked:
            continue
        try:
            earned = achievement.check_fn(db)
        except Exception as exc:
            logger.warning("Achievement check %s failed: %s", achievement.id, exc)
            continue
        if earned:
            try:
                db.execute(
                    text("""
                        INSERT INTO user_achievements (id, achievement_id, unlocked_at)
                        VALUES (:id, :achievement_id, :now)
                        ON CONFLICT(achievement_id) DO NOTHING
                    """),
                    {"id": str(uuid.uuid4()), "achievement_id": achievement.id, "now": datetime.now(timezone.utc)},
                )
                db.commit()
                newly_unlocked.append(achievement.id)
                logger.info("Achievement unlocked: %s", achievement.id)
            except Exception as exc:
                logger.warning("Could not save achievement %s: %s", achievement.id, exc)
                db.rollback()

    return newly_unlocked
