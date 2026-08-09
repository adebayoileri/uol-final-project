"""Certificate generation via WeasyPrint.

Generates a one-page PDF certificate for a completed course.
Caches the result; regenerates if mastery changed by >5%.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Course, Lesson, Module
from app.services.mastery import course_mastery

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).parent.parent.parent / "templates" / "certificate.html"
_CERT_DIR = Path(__file__).parent.parent.parent / "data" / "certificates"
_CERT_DIR.mkdir(parents=True, exist_ok=True)

_TEMPLATE = _TEMPLATE_PATH.read_text()


def _check_all_lessons_complete(course_id: str, db: Session) -> bool:
    row = db.execute(
        text("""
            SELECT COUNT(*) as incomplete
            FROM modules m
            JOIN lessons l ON l.module_id = m.id
            WHERE m.course_id = :cid AND l.completed_at IS NULL
        """),
        {"cid": course_id},
    ).fetchone()
    return row is not None and row.incomplete == 0


def generate_certificate(course_id: str, db: Session) -> bytes:
    """Return PDF bytes for a completed course.

    Raises HTTPException(400) if not all lessons are complete.
    """
    import weasyprint

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

    # Verify all lessons complete
    total_lessons = db.execute(
        text("""
            SELECT COUNT(*) as n FROM modules m
            JOIN lessons l ON l.module_id = m.id
            WHERE m.course_id = :cid
        """),
        {"cid": course_id},
    ).fetchone()

    if not total_lessons or total_lessons.n == 0:
        raise HTTPException(status_code=400, detail="Course has no lessons.")

    if not _check_all_lessons_complete(course_id, db):
        raise HTTPException(status_code=400, detail="Not all lessons are complete yet.")

    mastery_data = course_mastery(course_id, db)
    current_mastery = mastery_data["overall"]
    mastery_pct = round(current_mastery * 100, 1)

    # Check cache
    row = db.execute(
        text("SELECT mastery_snapshot, pdf_path FROM certificate_cache WHERE course_id = :cid"),
        {"cid": course_id},
    ).fetchone()

    if row:
        cached_mastery = row.mastery_snapshot
        # Only regenerate if mastery changed by >5%
        if abs(cached_mastery - current_mastery) <= 0.05:
            pdf_path = Path(row.pdf_path)
            if pdf_path.is_file():
                logger.info("Certificate cache hit for %s", course_id)
                return pdf_path.read_bytes()

    # Generate
    completion_date = datetime.now(timezone.utc).strftime("%B %d, %Y")
    rendered = (
        _TEMPLATE
        .replace("{{ course_title }}", course.title)
        .replace("{{ mastery_pct }}", str(mastery_pct))
        .replace("{{ completion_date }}", completion_date)
    )

    pdf_bytes = weasyprint.HTML(string=rendered).write_pdf()

    # Save
    pdf_path = _CERT_DIR / f"{course_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    db.execute(
        text("""
            INSERT INTO certificate_cache (course_id, mastery_snapshot, pdf_path, created_at)
            VALUES (:cid, :mastery, :path, :now)
            ON CONFLICT(course_id) DO UPDATE SET
                mastery_snapshot = excluded.mastery_snapshot,
                pdf_path = excluded.pdf_path,
                created_at = excluded.created_at
        """),
        {"cid": course_id, "mastery": current_mastery, "path": str(pdf_path), "now": datetime.now(timezone.utc)},
    )
    db.commit()

    return pdf_bytes
