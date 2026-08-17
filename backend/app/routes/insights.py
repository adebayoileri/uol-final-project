"""Learning insights endpoints.

GET /courses/{id}/insights — per-course insights bundle
GET /insights/study-time   — global optimal study time
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_course
from app.database import get_db
from app.models import Course, User
from app.services.insights import next_reviews, optimal_study_time, recommended_focus

router = APIRouter(tags=["insights"])


@router.get("/courses/{course_id}/insights")
def course_insights(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    get_owned_course(db, course_id, user.id)

    return {
        "optimal_study_time": optimal_study_time(db, user.id),
        "recommended_focus": recommended_focus(course_id, db),
        "next_reviews": next_reviews(course_id, db),
    }


@router.get("/insights/study-time")
def global_study_time(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    return {"optimal_study_time": optimal_study_time(db, user.id)}
