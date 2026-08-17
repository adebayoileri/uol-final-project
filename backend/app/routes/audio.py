"""Lesson narration generation endpoint.

POST /lessons/{id}/narration — synthesize (or return cached) lesson audio.
Returns: {"url": "/audio/<filename>"}

Language detection: courses in the "spanish" category get es_ES voice; all
others get en_US. Falls back gracefully if Piper voice not installed.
"""

import hashlib
import io
import logging
import wave
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.ownership import get_owned_lesson
from app.database import get_db
from app.models import Lesson, User
from app.services.content_parser import parse_lesson_body
from app.services.course_profile import profile_for_lesson
from app.services.tts import synthesize_speech

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/lessons", tags=["audio"])

_NARRATION_DIR = Path(__file__).parent.parent.parent / "data" / "narration"
_NARRATION_DIR.mkdir(parents=True, exist_ok=True)


def _detect_lang(lesson: Lesson) -> str:
    """Voice to narrate this lesson in.

    Delegates to the shared resolver, which reads goal/category/title together.
    Checking `category` alone missed a Spanish course filed under "Language",
    so it was narrated in an English voice.
    """
    return profile_for_lesson(lesson).tts_language


def _build_narration_text(lesson: Lesson) -> str:
    """Body content only — no title, no objectives, no spoken section headers.

    Narration should read the lesson, not announce its structure. The prose
    summary leads because it is genuine content and is the only content an
    unenriched lesson has, so narration degrades gracefully rather than going
    silent.
    """
    parsed = parse_lesson_body(lesson.content_json or "")
    parts: list[str] = []

    prose = (lesson.description or "").strip()
    if prose:
        parts.append(prose)

    for concept in parsed["key_concepts"]:
        name = concept.get("name", "").strip()
        definition = concept.get("definition", "").strip()
        example = concept.get("example", "").strip()
        if not (name and definition):
            continue
        # "open(). Opens a file and returns…" narrates as a natural sentence
        # pair, where "Key concept: open()" narrates as a heading read aloud.
        parts.append(f"{name}. {definition}")
        if example:
            parts.append(example)

    if parsed["worked_example"]:
        for line in parsed["worked_example"].splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts.append(line)

    for pitfall in parsed["common_pitfalls"]:
        pitfall = pitfall.strip()
        if pitfall:
            parts.append(pitfall)

    # practice_prompts are deliberately excluded: read aloud with no pause for
    # an answer, they only confuse.

    return " ".join(
        part if part.endswith((".", "!", "?")) else f"{part}."
        for part in parts
    )


def _chunk_text(text: str, max_len: int = 900) -> list[str]:
    """Split text at sentence boundaries to stay under max_len chars."""
    sentences = [s.strip() for s in text.replace("\n", " ").split(".") if s.strip()]
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current} {sentence}." if current else f"{sentence}."
        if len(candidate) > max_len and current:
            chunks.append(current)
            current = f"{sentence}."
        else:
            current = candidate
    if current:
        chunks.append(current)
    # Empty input must yield no chunks — [""] would hand piper an empty argument.
    return chunks or ([text[:max_len]] if text.strip() else [])


def _concat_wavs(wav_chunks: list[bytes]) -> bytes:
    """Concatenate multiple WAV blobs into one using stdlib wave module."""
    if len(wav_chunks) == 1:
        return wav_chunks[0]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as out:
        for i, chunk in enumerate(wav_chunks):
            with wave.open(io.BytesIO(chunk), "rb") as src:
                if i == 0:
                    out.setparams(src.getparams())
                out.writeframes(src.readframes(src.getnframes()))
    return buf.getvalue()


@router.post("/{lesson_id}/narration")
def generate_narration(
    lesson_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    lesson = get_owned_lesson(db, lesson_id, user.id)

    narration_text = _build_narration_text(lesson)
    # Before the cache lookup, so an empty lesson never writes a cache row.
    if not narration_text.strip():
        raise HTTPException(
            status_code=422,
            detail="This lesson has no content to narrate yet.",
        )

    content_hash = hashlib.sha256(narration_text.encode()).hexdigest()[:16]

    # Check cache (raw SQL — narration_cache is not an ORM model)
    from sqlalchemy import text as sql_text
    row = db.execute(
        sql_text("SELECT file_path, content_hash FROM narration_cache WHERE lesson_id = :id"),
        {"id": lesson_id},
    ).fetchone()

    if row and row.content_hash == content_hash:
        cached_path = Path(row.file_path)
        if cached_path.is_file():
            logger.info("narration cache hit: %s", lesson_id)
            return {"url": f"/audio/{cached_path.name}"}

    # Generate
    lang = _detect_lang(lesson)
    chunks = _chunk_text(narration_text)
    logger.info("Synthesising narration for %s (%d chunk(s), lang=%s)", lesson_id, len(chunks), lang)

    try:
        wav_chunks = [synthesize_speech(chunk, lang=lang) for chunk in chunks]
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    combined = _concat_wavs(wav_chunks)

    filename = f"{lesson_id}_{content_hash}.wav"
    file_path = _NARRATION_DIR / filename
    file_path.write_bytes(combined)

    db.execute(
        sql_text("""
            INSERT INTO narration_cache (lesson_id, content_hash, file_path, created_at)
            VALUES (:lesson_id, :hash, :path, :now)
            ON CONFLICT(lesson_id) DO UPDATE SET
                content_hash = excluded.content_hash,
                file_path = excluded.file_path,
                created_at = excluded.created_at
        """),
        {"lesson_id": lesson_id, "hash": content_hash, "path": str(file_path), "now": datetime.now(timezone.utc)},
    )
    db.commit()

    return {"url": f"/audio/{filename}"}
