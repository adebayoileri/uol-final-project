#!/usr/bin/env python
"""One-time script: create one FSRS Card row for every Question in the DB.
Safe to re-run — existing cards are skipped.
Usage (from backend/): python scripts/backfill_cards.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fsrs import Card as FSRSCard, Scheduler

from app.database import SessionLocal, create_tables
from app.models import Card as DBCard, Question


def main() -> None:
    create_tables()
    scheduler = Scheduler()
    db = SessionLocal()
    try:
        questions = db.query(Question).all()
        created = skipped = 0
        for q in questions:
            if db.query(DBCard).filter(DBCard.question_id == q.id).first():
                skipped += 1
                continue
            fsrs_card = FSRSCard()
            db.add(DBCard(
                question_id=q.id,
                state=int(fsrs_card.state),
                step=fsrs_card.step,
                stability=fsrs_card.stability,
                difficulty=fsrs_card.difficulty,
                due=fsrs_card.due.isoformat(),
                last_review=fsrs_card.last_review.isoformat() if fsrs_card.last_review else None,
            ))
            created += 1
        db.commit()
        print(f"Done: {created} created, {skipped} skipped.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
