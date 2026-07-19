import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload

from agents.course_agent import generate_course
from app.database import get_db
from app.models import Course, Lesson, Module, Objective
from app.schemas import (
    CourseSummaryResponse,
    CourseRequest,
    CourseResponse,
    LessonDetailResponse,
    ProgressSummary,
)
from app.services.embeddings import index_lesson
from app.services.progress import course_progress

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummaryResponse])
def list_courses(db: Session = Depends(get_db)) -> list[CourseSummaryResponse]:
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    result = []
    for course in courses:
        ps = course_progress(course.id, db)
        result.append(CourseSummaryResponse(
            id=course.id,
            title=course.title,
            category=course.category,
            created_at=course.created_at,
            progress_summary=ProgressSummary(**ps),
        ))
    return result


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(body: CourseRequest, db: Session = Depends(get_db)) -> CourseResponse:
    """Generate a structured course via Ollama and persist it to SQLite."""
    try:
        course_data = generate_course(
            goal=body.goal,
            duration=body.duration,
            category=body.category,
        )
    except RuntimeError as exc:
        logger.error("Course generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Course generation is temporarily unavailable. Please try again.",
        ) from exc

    course = Course(
        goal=body.goal,
        duration=body.duration,
        category=body.category,
        title=course_data["title"],
        description=course_data["description"],
    )

    for module_index, module_data in enumerate(course_data["modules"]):
        module = Module(
            course=course,
            order_index=module_index,
            title=module_data["title"],
            description=module_data.get("description", ""),
        )
        for lesson_index, lesson_data in enumerate(module_data.get("lessons", [])):
            lesson = Lesson(
                module=module,
                order_index=lesson_index,
                title=lesson_data["title"],
                description=lesson_data.get("description", ""),
                duration_minutes=int(lesson_data.get("duration_minutes", 45)),
            )
            for obj_index, obj_text in enumerate(lesson_data.get("objectives", [])):
                lesson.objectives.append(
                    Objective(
                        lesson=lesson,
                        order_index=obj_index,
                        description=str(obj_text),
                    )
                )
            module.lessons.append(lesson)
        course.modules.append(module)

    db.add(course)
    db.commit()
    db.refresh(course)

    for module in course.modules:
        for lesson in module.lessons:
            index_lesson(lesson, db)

    return CourseResponse.model_validate(course)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(course_id: str, db: Session = Depends(get_db)) -> CourseResponse:
    course = (
        db.query(Course)
        .options(
            selectinload(Course.modules)
            .selectinload(Module.lessons)
            .selectinload(Lesson.objectives)
        )
        .filter(Course.id == course_id)
        .first()
    )
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")
    return CourseResponse.model_validate(course)


@router.get("/{course_id}/lessons/{lesson_id}", response_model=LessonDetailResponse)
def get_lesson_detail(
    course_id: str, lesson_id: str, db: Session = Depends(get_db)
) -> LessonDetailResponse:
    lesson = (
        db.query(Lesson)
        .options(
            selectinload(Lesson.objectives),
            selectinload(Lesson.questions),
        )
        .join(Module, Module.id == Lesson.module_id)
        .filter(Module.course_id == course_id, Lesson.id == lesson_id)
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return LessonDetailResponse.model_validate(lesson)
