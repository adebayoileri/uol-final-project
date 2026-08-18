"""Certificate generation.

Produces a one-page A4 landscape PDF for a completed course, cached on disk and
regenerated when mastery moves by more than 5%.

Drawn with fpdf2 rather than rendered from HTML. The previous implementation
used WeasyPrint, which needs Pango, GLib and cairo installed as *system*
libraries — a dependency `pyproject.toml` cannot express and the README never
mentioned. The result was a feature that had never once worked on a machine
without them: `import weasyprint` raised `OSError` on the first line of the
generator, and because nothing caught it the response escaped past the CORS
middleware and reached the browser with no status at all. fpdf2 is pure Python,
so `uv sync` is now genuinely the whole setup.

Laying the page out in code rather than in CSS also removes an injection path:
the old renderer substituted an LLM-generated course title into an HTML string
with `str.replace` and no escaping.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from fpdf import FPDF
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import Course
from app.services.mastery import course_mastery

logger = logging.getLogger(__name__)

_CERT_DIR = Path(__file__).parent.parent.parent / "data" / "certificates"
_CERT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_RECIPIENT = "The Learner"

# A4 landscape, in mm.
_PAGE_W = 297.0
_PAGE_H = 210.0

# Carried over from the retired HTML template so the artefact looks unchanged.
_PARCHMENT = (248, 244, 238)
_INK = (44, 26, 14)
_INK_SOFT = (90, 64, 48)
_GOLD = (122, 92, 54)
_RULE = (192, 160, 112)
_BORDER = (76, 58, 36)

# Substitutions for characters a core PDF font cannot encode. Course titles and
# names are user- or model-supplied, so a smart quote or an em dash is routine —
# and would otherwise raise rather than degrade.
_TRANSLITERATE = str.maketrans({
    "—": "-", "–": "-", "‘": "'", "’": "'",
    "“": '"', "”": '"', "…": "...", " ": " ",
})


def _encodable(value: str) -> str:
    """Coerce text into something the built-in Times face can render."""
    return value.translate(_TRANSLITERATE).encode("latin-1", "replace").decode("latin-1")


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


def _centred(
    pdf: FPDF,
    y: float,
    body: str,
    size: float,
    *,
    style: str = "",
    colour: tuple[int, int, int] = _INK,
    spacing: float = 0.0,
    max_width: float = 240.0,
    min_size: float = 8.0,
) -> None:
    """Draw one centred line, shrinking it to fit rather than overflowing.

    Shrink-to-fit keeps every element at a fixed y, so a long course title
    cannot push the date off the page. Titles are generated, so their length is
    not something the layout can assume.
    """
    body = _encodable(body)
    pdf.set_text_color(*colour)
    pdf.set_char_spacing(spacing)

    while size > min_size:
        pdf.set_font("Times", style, size)
        if pdf.get_string_width(body) <= max_width:
            break
        size -= 0.5
    else:
        pdf.set_font("Times", style, min_size)

    # Past the floor the string is genuinely too long; truncate so it stays
    # inside the border instead of running over it. The ellipsis is ASCII and
    # added only at the end: appending an encodable "…" inside the loop would
    # expand to three characters and make the string grow rather than shrink.
    if pdf.get_string_width(body) > max_width:
        keep = len(body)
        while keep > 1 and pdf.get_string_width(body[:keep] + "...") > max_width:
            keep -= 1
        body = body[:keep].rstrip() + "..."

    pdf.set_xy(0, y)
    pdf.cell(_PAGE_W, 8, body, align="C")
    pdf.set_char_spacing(0)


def _rule(pdf: FPDF, y: float, width: float = 120.0) -> None:
    pdf.set_draw_color(*_RULE)
    pdf.set_line_width(0.3)
    pdf.line((_PAGE_W - width) / 2, y, (_PAGE_W + width) / 2, y)


def render_certificate_pdf(course_title: str, mastery_pct: float, recipient: str) -> bytes:
    """Draw the certificate. Pure function — no database, no filesystem."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()

    pdf.set_fill_color(*_PARCHMENT)
    pdf.rect(0, 0, _PAGE_W, _PAGE_H, style="F")

    pdf.set_draw_color(*_BORDER)
    pdf.set_line_width(2.1)
    pdf.rect((_PAGE_W - 280) / 2, (_PAGE_H - 193) / 2, 280, 193)
    pdf.set_line_width(0.5)
    pdf.rect((_PAGE_W - 270) / 2, (_PAGE_H - 183) / 2, 270, 183)

    completion_date = datetime.now(timezone.utc).strftime("%B %d, %Y")

    _centred(pdf, 48, "CERTIFICATE OF COMPLETION", 11, colour=_GOLD, spacing=1.4)
    _centred(pdf, 60, "AI Course Agent", 28, spacing=0.6)
    _rule(pdf, 82)
    _centred(pdf, 88, "THIS CERTIFICATE IS AWARDED TO", 10, colour=_INK_SOFT, spacing=1.0)
    _centred(pdf, 97, recipient, 20, style="I")
    _centred(pdf, 112, "for successfully completing", 10, colour=_INK_SOFT)
    _centred(pdf, 120, course_title, 15, style="B")
    _centred(pdf, 133, f"Mastery achieved: {mastery_pct}%", 10, colour=_GOLD)
    _rule(pdf, 146)
    _centred(pdf, 151, f"Completed on {completion_date}", 10, colour=_GOLD, spacing=0.6)

    return bytes(pdf.output())


def generate_certificate(
    course_id: str,
    db: Session,
    recipient: str = DEFAULT_RECIPIENT,
) -> bytes:
    """Return PDF bytes for a completed course.

    Raises HTTPException(400) if not all lessons are complete, and 503 if the
    PDF cannot be produced. The 503 matters: an uncaught exception here is not
    handled by the CORS middleware, so the browser blocks the response and the
    client sees a network error with no status to report.
    """
    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found.")

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

    row = db.execute(
        text("""
            SELECT mastery_snapshot, pdf_path, recipient
            FROM certificate_cache WHERE course_id = :cid
        """),
        {"cid": course_id},
    ).fetchone()

    if row:
        # The recipient is part of the key, not just mastery: someone who sets
        # their display name after generating would otherwise keep a stale
        # certificate addressed to "The Learner" indefinitely.
        same_recipient = (row.recipient or DEFAULT_RECIPIENT) == recipient
        if same_recipient and abs(row.mastery_snapshot - current_mastery) <= 0.05:
            pdf_path = Path(row.pdf_path)
            if pdf_path.is_file():
                logger.info("Certificate cache hit for %s", course_id)
                return pdf_path.read_bytes()

    try:
        pdf_bytes = render_certificate_pdf(course.title, mastery_pct, recipient)
    except Exception as exc:  # noqa: BLE001 — surfaced, not swallowed
        logger.exception("Certificate rendering failed for %s", course_id)
        raise HTTPException(
            status_code=503,
            detail="The certificate could not be generated. Please try again.",
        ) from exc

    pdf_path = _CERT_DIR / f"{course_id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    db.execute(
        text("""
            INSERT INTO certificate_cache
                (course_id, mastery_snapshot, pdf_path, created_at, recipient)
            VALUES (:cid, :mastery, :path, :now, :recipient)
            ON CONFLICT(course_id) DO UPDATE SET
                mastery_snapshot = excluded.mastery_snapshot,
                pdf_path = excluded.pdf_path,
                created_at = excluded.created_at,
                recipient = excluded.recipient
        """),
        {
            "cid": course_id,
            "mastery": current_mastery,
            "path": str(pdf_path),
            "now": datetime.now(timezone.utc),
            "recipient": recipient,
        },
    )
    db.commit()

    return pdf_bytes
