import json
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.content_parser import parse_lesson_body


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Stored already normalised (stripped + lowercased) so the UNIQUE constraint
    # is meaningful — "Bayo@X.com " and "bayo@x.com" must be one account.
    email: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # Nullable, and honestly so: accounts created before this column existed
    # have no name and nothing can invent one for them. Required at
    # registration, absent for legacy rows, and rendered with an email fallback.
    name: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class AuthSession(Base):
    """Server-side login session.

    Named `auth_sessions` to avoid confusion with the unrelated `study_sessions`
    table, which tracks 10-minute windows of learning activity. Server-side
    rather than a JWT so logout can actually revoke.
    """

    __tablename__ = "auth_sessions"

    # The opaque token held in the cookie. Not derived from anything.
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    # Nullable in the column so SQLite can add it to the populated dev database;
    # every fresh install gets NOT NULL from create_all. create_course is the
    # only writer and always sets it.
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    duration: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    modules: Mapped[list["Module"]] = relationship(
        "Module", back_populates="course", cascade="all, delete-orphan", order_by="Module.order_index"
    )


class Module(Base):
    __tablename__ = "modules"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(Text, ForeignKey("courses.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    course: Mapped["Course"] = relationship("Course", back_populates="modules")
    lessons: Mapped[list["Lesson"]] = relationship(
        "Lesson", back_populates="module", cascade="all, delete-orphan", order_by="Lesson.order_index"
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    module_id: Mapped[str] = mapped_column(Text, ForeignKey("modules.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Deep teaching content (key concepts, worked example, pitfalls, practice
    # prompts) as a JSON object, generated lazily on first open. Kept separate
    # from `description` because that column feeds question prompts verbatim and
    # is indexed for search — JSON in either place would be a regression.
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Diagram specifications as a JSON array, generated lazily after enrichment.
    # NULL and '[]' mean different things: NULL is "not attempted", '[]' is
    # "attempted, and no diagram helps this lesson" — a cacheable answer.
    diagram_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Listening clues as a JSON object mapping concept name → description, for
    # the aural drill. Generated lazily after enrichment, on the same model as
    # diagram_json. It lives in its own column rather than inside content_json
    # for two reasons: regenerating a clue then cannot churn the lesson body or
    # orphan the diagram generated from it, and the lesson-detail schema — which
    # enumerates its fields explicitly — has no path to leak a clue to a client
    # that could read it instead of listening.
    clues_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    module: Mapped["Module"] = relationship("Module", back_populates="lessons")
    objectives: Mapped[list["Objective"]] = relationship(
        "Objective", back_populates="lesson", cascade="all, delete-orphan", order_by="Objective.order_index"
    )
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="lesson", cascade="all, delete-orphan", order_by="Question.order_index"
    )

    @property
    def content(self) -> dict | None:
        """Parsed structured content, or None if this lesson isn't enriched yet.

        Pydantic reads properties under `from_attributes=True`, so declaring
        `content` on a response schema is enough to expose this — no route
        changes needed.
        """
        if not self.content_json:
            return None
        parsed = parse_lesson_body(self.content_json)
        return {k: v for k, v in parsed.items() if k != "is_structured"}

    @property
    def diagrams(self) -> list[dict] | None:
        """Parsed diagram specs, or None if generation has not been attempted.

        Tolerant by design: a row that somehow holds unparseable JSON reads as
        "no diagrams" rather than breaking the lesson page, which is the same
        bargain `content` makes.
        """
        if self.diagram_json is None:
            return None
        try:
            parsed = json.loads(self.diagram_json)
        except (TypeError, ValueError):
            return []
        return parsed if isinstance(parsed, list) else []

    @property
    def clues(self) -> dict[str, str] | None:
        """Listening clues keyed by casefolded concept name, or None if never attempted.

        Casefolded on the way out because the lookup is by the concept name the
        drill holds, and the model is free to return "Overfitting" where the
        lesson says "overfitting". Tolerant of unparseable JSON for the same
        reason `diagrams` is: a bad row should cost the aural drill, not the
        lesson page.
        """
        if self.clues_json is None:
            return None
        try:
            parsed = json.loads(self.clues_json)
        except (TypeError, ValueError):
            return {}
        if not isinstance(parsed, dict):
            return {}
        raw = parsed.get("clues")
        if not isinstance(raw, dict):
            return {}
        return {
            str(name).casefold(): str(clue)
            for name, clue in raw.items()
            if str(name).strip() and str(clue).strip()
        }


class Objective(Base):
    __tablename__ = "objectives"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(Text, ForeignKey("lessons.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="objectives")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    lesson_id: Mapped[str] = mapped_column(Text, ForeignKey("lessons.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_answer: Mapped[str] = mapped_column(Text, nullable=False)
    reference_embedding: Mapped[str] = mapped_column(Text, nullable=False)  # JSON float list
    question_type: Mapped[str] = mapped_column(Text, nullable=False, default="open")
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    course_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    lesson: Mapped["Lesson"] = relationship("Lesson", back_populates="questions")
    card: Mapped["Card | None"] = relationship("Card", back_populates="question", uselist=False)


class Card(Base):
    __tablename__ = "cards"
    __table_args__ = (UniqueConstraint("question_id", name="uq_cards_question_id"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(Text, ForeignKey("questions.id"), nullable=False)
    state: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    step: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)
    due: Mapped[str] = mapped_column(Text, nullable=False)           # ISO 8601 UTC
    last_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    course_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    question: Mapped["Question"] = relationship("Question", back_populates="card")
    reviews: Mapped[list["Review"]] = relationship(
        "Review", back_populates="card", cascade="all, delete-orphan"
    )


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    card_id: Mapped[str] = mapped_column(Text, ForeignKey("cards.id"), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    stability: Mapped[float | None] = mapped_column(Float, nullable=True)
    difficulty: Mapped[float | None] = mapped_column(Float, nullable=True)

    card: Mapped["Card"] = relationship("Card", back_populates="reviews")


class ContentEmbedding(Base):
    __tablename__ = "content_embeddings"
    __table_args__ = (UniqueConstraint("content_type", "content_id", name="uq_content_embeddings"),)

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    content_type: Mapped[str] = mapped_column(Text, nullable=False)    # "lesson" | "question"
    content_id: Mapped[str] = mapped_column(Text, nullable=False)       # lesson.id or question.id
    content_text: Mapped[str] = mapped_column(Text, nullable=False)     # display text for results
    course_id: Mapped[str] = mapped_column(Text, nullable=False)        # for scope filtering + linking
    lesson_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # for questions → their lesson
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)  # numpy float32 BLOB (1536 bytes)
