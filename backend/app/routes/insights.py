"""Learning insights endpoints.

GET /courses/{id}/insights — per-course insights bundle
GET /insights/study-time   — global optimal study time
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course
from app.services.insights import next_reviews, optimal_study_time, recommended_focus

router = APIRouter(tags=["insights"])


@router.get("/courses/{course_id}/insights")
def course_insights(course_id: str, db: Session = Depends(get_db)):
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    return {
        "optimal_study_time": optimal_study_time(db),
        "recommended_focus": recommended_focus(course_id, db),
        "next_reviews": next_reviews(course_id, db),
    }


@router.get("/insights/study-time")
def global_study_time(db: Session = Depends(get_db)):
    return {"optimal_study_time": optimal_study_time(db)}
