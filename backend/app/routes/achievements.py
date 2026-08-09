"""Achievement endpoints.

GET /achievements         — all achievements with unlocked status
GET /achievements/recent  — achievements unlocked after ?since=<iso>
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.achievements.catalogue import CATALOGUE
from app.database import get_db

router = APIRouter(prefix="/achievements", tags=["achievements"])


@router.get("")
def list_achievements(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("SELECT achievement_id, unlocked_at FROM user_achievements")
        ).fetchall()
        unlocked_map = {r.achievement_id: r.unlocked_at for r in rows}
    except Exception:
        unlocked_map = {}

    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "icon": a.icon,
            "unlocked": a.id in unlocked_map,
            "unlocked_at": unlocked_map.get(a.id),
        }
        for a in CATALOGUE
    ]


@router.get("/recent")
def recent_achievements(
    since: str = Query(..., description="ISO 8601 timestamp"),
    db: Session = Depends(get_db),
):
    try:
        rows = db.execute(
            text("""
                SELECT achievement_id, unlocked_at FROM user_achievements
                WHERE unlocked_at > :since ORDER BY unlocked_at DESC
            """),
            {"since": since},
        ).fetchall()
    except Exception:
        return []

    unlocked_ids = {r.achievement_id for r in rows}
    unlocked_at = {r.achievement_id: r.unlocked_at for r in rows}

    return [
        {
            "id": a.id,
            "title": a.title,
            "description": a.description,
            "icon": a.icon,
            "unlocked": True,
            "unlocked_at": unlocked_at.get(a.id),
        }
        for a in CATALOGUE
        if a.id in unlocked_ids
    ]
