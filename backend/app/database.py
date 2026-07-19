import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_DEFAULT_DB_PATH = Path(__file__).parent.parent / "course_agent.db"
_DB_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DEFAULT_DB_PATH}")

engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def _run_migrations() -> None:
    with engine.connect() as conn:
        for stmt in [
            "ALTER TABLE questions ADD COLUMN question_type TEXT NOT NULL DEFAULT 'open'",
            "ALTER TABLE questions ADD COLUMN code_snippet TEXT",
            "ALTER TABLE questions ADD COLUMN course_id TEXT",
            "ALTER TABLE cards ADD COLUMN course_id TEXT",
            "ALTER TABLE lessons ADD COLUMN completed_at DATETIME",
        ]:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists

        # Backfill course_id on existing rows via the lesson → module chain
        conn.execute(text("""
            UPDATE questions
            SET course_id = (
                SELECT modules.course_id
                FROM lessons
                JOIN modules ON modules.id = lessons.module_id
                WHERE lessons.id = questions.lesson_id
            )
            WHERE course_id IS NULL
        """))
        conn.execute(text("""
            UPDATE cards
            SET course_id = (
                SELECT modules.course_id
                FROM questions
                JOIN lessons ON lessons.id = questions.lesson_id
                JOIN modules ON modules.id = lessons.module_id
                WHERE questions.id = cards.question_id
            )
            WHERE course_id IS NULL
        """))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_cards_course_due ON cards (course_id, due)"
        ))
        conn.commit()


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
