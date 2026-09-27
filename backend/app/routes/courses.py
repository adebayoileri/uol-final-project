import logging
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload

from agents.course_agent import generate_course
from app.auth.deps import current_user
from app.auth.ownership import get_owned_course, get_owned_lesson
from app.database import get_db
from app.models import Course, Lesson, Module, Objective, User
from app.schemas import (
    CategoryOption,
    CategorySuggestionRequest,
    CategorySuggestionResponse,
    CourseSummaryResponse,
    CourseRequest,
    CourseResponse,
    LessonDetailResponse,
    ProgressSummary,
)
from app.services.categorizer import CATEGORIES, resolve_category, suggest_category
from app.services.certificates import DEFAULT_RECIPIENT, generate_certificate
from app.services.embeddings import index_lesson
from app.services.events import COURSE_GENERATED, record_event
from app.services.mastery import course_mastery
from app.services.progress import course_progress
from app.services.streaks import current_streak

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=list[CourseSummaryResponse])
def list_courses(
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> list[CourseSummaryResponse]:
    courses = (
        db.query(Course)
        .filter(Course.user_id == user.id)
        .order_by(Course.created_at.desc())
        .all()
    )
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


@router.get("/categories", response_model=list[CategoryOption])
def list_categories(user: User = Depends(current_user)) -> list[CategoryOption]:
    """The category vocabulary the form offers.

    Served rather than duplicated in the client so the dropdown, the "Auto"
    classifier and the value the create endpoint validates against are the same
    list by construction. Two copies of a taxonomy drift, and the failure is
    silent — a category the form offers but the resolver does not recognise.

    Declared above `/{course_id}`: FastAPI matches in registration order, and a
    literal path registered after the parameterised one is unreachable.
    """
    return [
        CategoryOption(value=c.value, label=c.display, group=c.group, note=c.note)
        for c in CATEGORIES
    ]


@router.post("/category-suggestion", response_model=CategorySuggestionResponse)
def suggest_course_category(
    body: CategorySuggestionRequest,
    user: User = Depends(current_user),
) -> CategorySuggestionResponse:
    """Guess a category from a goal, for the form to show before submitting.

    A preview only — the learner can override it, and `create_course` resolves
    independently so a course can still be generated if this call never lands.
    """
    suggestion = suggest_category(body.goal)
    return CategorySuggestionResponse(
        value=suggestion.value,
        label=suggestion.label,
        group=suggestion.group,
        note=suggestion.note,
        source=suggestion.source,
    )


@router.post("", response_model=CourseResponse, status_code=201)
def create_course(
    body: CourseRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CourseResponse:
    """Generate a structured course via Ollama and persist it to SQLite."""
    category = resolve_category(body.category, body.goal)
    try:
        course_data = generate_course(
            goal=body.goal,
            duration=body.duration,
            category=category,
        )
    except RuntimeError as exc:
        logger.error("Course generation failed: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Course generation is temporarily unavailable. Please try again.",
        ) from exc

    course = Course(
        user_id=user.id,
        goal=body.goal,
        duration=body.duration,
        category=category,
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

    record_event(
        db,
        COURSE_GENERATED,
        {"course_id": course.id, "category": course.category},
        user_id=user.id,
    )
    return CourseResponse.model_validate(course)


@router.get("/{course_id}", response_model=CourseResponse)
def get_course(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> CourseResponse:
    course = get_owned_course(
        db,
        course_id,
        user.id,
        selectinload(Course.modules)
        .selectinload(Module.lessons)
        .selectinload(Lesson.objectives),
    )
    return CourseResponse.model_validate(course)


@router.get("/{course_id}/mastery")
def get_mastery(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    get_owned_course(db, course_id, user.id)
    return course_mastery(course_id, db)


@router.get("/{course_id}/timeline")
def get_timeline(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    course = get_owned_course(
        db,
        course_id,
        user.id,
        selectinload(Course.modules).selectinload(Module.lessons),
    )

    modules_out = []
    total_minutes = 0
    completed_minutes = 0

    for module in sorted(course.modules, key=lambda m: m.order_index):
        lessons_out = []
        for lesson in sorted(module.lessons, key=lambda l: l.order_index):
            dur = lesson.duration_minutes or 0
            total_minutes += dur
            if lesson.completed_at:
                completed_minutes += dur
            lessons_out.append({
                "id": lesson.id,
                "title": lesson.title,
                "duration_minutes": dur,
                "completed_at": lesson.completed_at.isoformat() if lesson.completed_at else None,
                "order_index": lesson.order_index,
            })
        modules_out.append({"title": module.title, "lessons": lessons_out})

    return {
        "modules": modules_out,
        "total_minutes": total_minutes,
        "completed_minutes": completed_minutes,
        "streak": current_streak(db, user.id),
    }


def _certificate_filename(course_title: str) -> str:
    """A saved certificate should be recognisable in a downloads folder.

    Restricted to ASCII word characters and hyphens because Content-Disposition
    is a header: a quote or a newline in a generated course title would
    otherwise let the title break out of the header value.
    """
    slug = re.sub(r"[^A-Za-z0-9]+", "-", course_title).strip("-").lower()
    return f"certificate-{slug[:60] or 'course'}.pdf"


@router.get("/{course_id}/certificate")
def get_certificate(
    course_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    course = get_owned_course(db, course_id, user.id)
    # getattr rather than user.name: the test suite injects a SimpleNamespace
    # stand-in for the authenticated user, and a missing attribute here would
    # turn every certificate test into a 500.
    recipient = (getattr(user, "name", None) or "").strip() or DEFAULT_RECIPIENT
    pdf_bytes = generate_certificate(course_id, db, recipient=recipient)

    filename = _certificate_filename(course.title)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{course_id}/lessons/{lesson_id}", response_model=LessonDetailResponse)
def get_lesson_detail(
    course_id: str,
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
) -> LessonDetailResponse:
    lesson = (
        db.query(Lesson)
        .options(
            selectinload(Lesson.objectives),
            selectinload(Lesson.questions),
        )
        .join(Module, Module.id == Lesson.module_id)
        .join(Course, Course.id == Module.course_id)
        .filter(
            Module.course_id == course_id,
            Lesson.id == lesson_id,
            Course.user_id == user.id,
        )
        .first()
    )
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    return LessonDetailResponse.model_validate(lesson)
