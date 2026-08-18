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
            # Diagram specs, generated lazily after enrichment. NULL means "not
            # attempted"; '[]' means "attempted, no diagram helps here".
            "ALTER TABLE lessons ADD COLUMN diagram_json TEXT",
            # Ownership. Nullable at the column level because SQLite cannot add
            # a NOT NULL column to a populated table; the ORM declares it
            # non-null, and fresh installs get the real constraint from
            # create_all. scripts/seed_user.py adopts the legacy rows.
            "ALTER TABLE courses ADD COLUMN user_id TEXT",
            "ALTER TABLE user_events ADD COLUMN user_id TEXT",
            # Display name, captured at registration. Nullable because accounts
            # that predate it genuinely have none.
            "ALTER TABLE users ADD COLUMN name TEXT",
            "ALTER TABLE study_sessions ADD COLUMN user_id TEXT",
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
                    user_id TEXT,
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
                    user_id TEXT,
                    started_at DATETIME NOT NULL,
                    last_activity_at DATETIME NOT NULL,
                    event_count INTEGER NOT NULL DEFAULT 0
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Achievements table.
        # The original schema had achievement_id UNIQUE globally, which meant
        # the first user to unlock an achievement permanently blocked everyone
        # else. Rebuild it with a composite unique. Guarded on the schema
        # itself so this is idempotent: it fires once on a legacy database,
        # never on a fresh one, and never again afterwards.
        try:
            cols = {
                r[1]
                for r in conn.execute(text("PRAGMA table_info(user_achievements)")).fetchall()
            }
            if cols and "user_id" not in cols:
                conn.execute(text("DROP TABLE user_achievements"))
                conn.commit()

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_achievements (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    achievement_id TEXT NOT NULL,
                    unlocked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE (user_id, achievement_id)
                )
            """))
            conn.commit()
        except Exception:
            pass

        # Ownership indexes
        for stmt in [
            "CREATE INDEX IF NOT EXISTS ix_courses_user ON courses (user_id)",
            "CREATE INDEX IF NOT EXISTS ix_events_user_time ON user_events (user_id, occurred_at)",
            "CREATE INDEX IF NOT EXISTS ix_sessions_user_last ON study_sessions (user_id, last_activity_at)",
            "CREATE INDEX IF NOT EXISTS ix_auth_sessions_user ON auth_sessions (user_id)",
        ]:
            try:
                conn.execute(text(stmt))
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
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    recipient TEXT
                )
            """))
            conn.commit()
        except Exception:
            pass

        # certificate_cache predates the recipient column. It is part of the
        # cache key, so without it someone who sets a display name would keep a
        # certificate addressed to "The Learner" for as long as mastery held.
        try:
            conn.execute(text("ALTER TABLE certificate_cache ADD COLUMN recipient TEXT"))
            conn.commit()
        except Exception:
            pass  # column already exists


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
