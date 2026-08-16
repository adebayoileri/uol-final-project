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
            # Structured lesson body, generated lazily on first open.
            # NULL means "not yet enriched" — an explicit state, not inferred.
            "ALTER TABLE lessons ADD COLUMN content_json TEXT",
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
        # Supports the review hub's created-date filter.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_cards_created ON cards (created_at)"
        ))
        # Narration cache table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS narration_cache (
                    lesson_id TEXT PRIMARY KEY,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Chat history table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS lesson_chat_messages (
                    id TEXT PRIMARY KEY,
                    lesson_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_chat_lesson ON lesson_chat_messages (lesson_id, created_at)"
            ))
            conn.commit()
        except Exception:
            pass

        # Behavioural event tables
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id TEXT PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    occurred_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT NOT NULL DEFAULT '{}'
                )
            """))
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_events_type_time ON user_events (event_type, occurred_at)"
            ))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    id TEXT PRIMARY KEY,
                    started_at DATETIME NOT NULL,
                    last_activity_at DATETIME NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Achievements table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id TEXT PRIMARY KEY,
                    achievement_id TEXT NOT NULL UNIQUE,
                    unlocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Certificate cache table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS certificate_cache (
                    course_id TEXT PRIMARY KEY,
                    mastery_snapshot REAL NOT NULL,
                    pdf_path TEXT NOT NULL,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
            conn.commit()
        except Exception:
            pass


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
