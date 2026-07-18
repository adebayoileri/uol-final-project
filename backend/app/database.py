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
        ]:
            try:
                conn.execute(text(stmt))
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
