import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, LargeBinary, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
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

    module: Mapped["Module"] = relationship("Module", back_populates="lessons")
    objectives: Mapped[list["Objective"]] = relationship(
        "Objective", back_populates="lesson", cascade="all, delete-orphan", order_by="Objective.order_index"
    )
    questions: Mapped[list["Question"]] = relationship(
        "Question", back_populates="lesson", cascade="all, delete-orphan", order_by="Question.order_index"
    )


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
