"""Drop cached diagrams that no longer pass validation.

    uv run python -m scripts.revalidate_diagrams --dry-run
    uv run python -m scripts.revalidate_diagrams

`lessons.diagram_json` is written once and cached forever, so a diagram stored
under looser rules survives every later tightening of those rules. That is not
hypothetical: a lesson on the perceptron had a chessboard with a knight on d4
cached against it, which passed every check that existed when it was generated.

Setting the column back to NULL is exactly the "never attempted" state, so the
lesson regenerates under the current rules the next time it is opened. Nothing
is deleted that cannot be recreated, and a lesson that legitimately has no
diagram ('[]') is left alone unless its content fails outright.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import SessionLocal, create_tables  # noqa: E402
from app.diagram_spec import validate_diagrams  # noqa: E402
from app.models import Lesson  # noqa: E402


def _reason(exc: Exception) -> str:
    """The human half of a Pydantic error, without its documentation URL."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        messages = [str(e.get("msg", "")).removeprefix("Value error, ") for e in errors()]
        if messages:
            return "; ".join(m for m in messages if m)[:160]
    return str(exc).splitlines()[0][:160]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be cleared without writing anything.",
    )
    args = parser.parse_args()

    create_tables()
    db = SessionLocal()
    cleared = kept = 0

    try:
        lessons = db.query(Lesson).filter(Lesson.diagram_json.isnot(None)).all()
        print(f"Checking {len(lessons)} lesson(s) with cached diagrams.\n")

        for lesson in lessons:
            try:
                stored = json.loads(lesson.diagram_json)
            except ValueError:
                stored = None

            course = lesson.module.course if lesson.module else None
            label = f"{course.title if course else '?'} / {lesson.title}"

            if not stored:
                kept += 1
                continue

            try:
                validate_diagrams({"diagrams": stored}, course=course)
            except Exception as exc:
                kinds = ", ".join(d.get("kind", "?") for d in stored)
                print(f"  CLEAR  {label}\n         [{kinds}] {_reason(exc)}")
                if not args.dry_run:
                    lesson.diagram_json = None
                cleared += 1
            else:
                kept += 1

        if not args.dry_run:
            db.commit()

        verb = "would be cleared" if args.dry_run else "cleared"
        print(f"\n{cleared} {verb}, {kept} still valid.")
        if cleared and args.dry_run:
            print("Re-run without --dry-run to apply.")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
