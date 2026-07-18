from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import SearchResultItem
from app.services.embeddings import search as _search

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResultItem])
def search_endpoint(
    q: str = Query(min_length=1, max_length=500),
    k: int = Query(default=5, ge=1, le=20),
    course_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[SearchResultItem]:
    return _search(q, k, db, course_id=course_id)
