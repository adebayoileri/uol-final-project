"""Write listening clues for lessons whose content predates the clue pass.

    uv run python -m scripts.backfill_lesson_clues --dry-run
    uv run python -m scripts.backfill_lesson_clues
    uv run python -m scripts.backfill_lesson_clues --course-id <id> --force

`clues_json` is written once and cached, and the clue pass only runs when a
lesson is opened. So every lesson enriched before the listening drill stopped
speaking its own answer has no clue, and the choice drills report themselves
unavailable for it. This walks those lessons and generates the missing clues.

Two kinds of lesson are incomplete, and both are picked up here. The first has
no clue set at all. The second has a set that is short of its concepts, because
validation drops any description that names its own term — a lesson can only get
so far when one concept's clue is rejected, and since the column is then
non-NULL, `ensure_clues` will never try again on its own. That case regenerates
the set and keeps it **only if it covers more concepts**, so a retry can improve
a lesson and can never make it worse.

It deliberately touches only `clues_json`. Regenerating the lesson body would
also have been a way to get clues, but it would rewrite the prose the report
describes, orphan every cached diagram, and invalidate the narration audio and
the committed figures — to add one field. The clue generator takes the stored
body as its input, so there is no need.

`--dry-run` calls no model: it reports what would be generated and stops.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import selectinload  # noqa: E402

from app.database import SessionLocal, create_tables  # noqa: E402
from app.models import Lesson, Module  # noqa: E402
from app.services.clue_generator import ensure_clues, generate_clues  # noqa: E402
from app.services.content_parser import parse_lesson_body  # noqa: E402


def _concept_count(lesson: Lesson) -> int:
    parsed = parse_lesson_body(lesson.content_json or "")
    return sum(1 for c in parsed["key_concepts"] if c["name"])


def _clue_count(lesson: Lesson) -> int:
    return len(lesson.clues or {})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be generated without calling the model or writing.",
    )
    parser.add_argument(
        "--course-id",
        default=None,
        help="Restrict to one course.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Stop after this many lessons (useful for a first, cheap pass).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate every set, not just the missing and short ones.",
    )
    args = parser.parse_args()

    create_tables()
    db = SessionLocal()
    written = skipped = failed = kept = 0

    try:
        query = (
            db.query(Lesson)
            .join(Module, Module.id == Lesson.module_id)
            .options(selectinload(Lesson.module).selectinload(Module.course))
            .order_by(Lesson.order_index)
        )
        if args.course_id:
            query = query.filter(Module.course_id == args.course_id)

        candidates = [
            lesson
            for lesson in query.all()
            if lesson.content_json
            and (
                args.force
                or lesson.clues_json is None
                or _clue_count(lesson) < _concept_count(lesson)
            )
        ]
        if args.limit is not None:
            candidates = candidates[: args.limit]

        if not candidates:
            print("Every enriched lesson has a clue for each of its concepts. Nothing to do.")
            return 0

        print(f"{len(candidates)} lesson(s) need clues.\n")

        for index, lesson in enumerate(candidates, start=1):
            course = lesson.module.course if lesson.module else None
            label = f"{course.title if course else '?'} / {lesson.title}"
            have, want = _clue_count(lesson), _concept_count(lesson)
            gap = f" [{have}/{want} concepts]" if lesson.clues_json is not None else ""
            print(f"  [{index}/{len(candidates)}] {label}{gap}", flush=True)

            if args.dry_run:
                skipped += 1
                continue

            if lesson.clues_json is None:
                # Never attempted: the normal path. Never raises.
                if ensure_clues(lesson, db) is None:
                    print("         FAILED — left for a later run")
                    failed += 1
                else:
                    print("         written")
                    written += 1
                continue

            # Already cached but short. Regenerate and keep the better set, so a
            # retry can only help — losing an existing description because a
            # second sample happened to be worse would be a regression.
            try:
                regenerated = generate_clues(lesson)
            except RuntimeError as exc:
                print(f"         FAILED — {exc}")
                failed += 1
                continue

            if len(regenerated) > have:
                lesson.clues_json = json.dumps({"clues": regenerated}, ensure_ascii=False)
                db.commit()
                print(f"         filled gaps: {have} → {len(regenerated)} concepts")
                written += 1
            else:
                print(f"         kept the existing {have} (retry covered {len(regenerated)})")
                kept += 1

        if args.dry_run:
            print(f"\n{skipped} lesson(s) would be generated. Nothing was written.")
            print("Re-run without --dry-run to apply.")
            return 0

        print(f"\n{written} written, {kept} kept as they were, {failed} failed.")
        if failed:
            # A non-zero exit so a partial run is not mistaken for a clean one.
            print("Re-run to retry the failures; successful lessons are skipped.")
            return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
