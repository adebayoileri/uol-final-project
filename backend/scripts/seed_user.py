"""Create the seed account and adopt all pre-auth data into it.

The application was single-user before authentication existed, so every course,
event and study session in an existing database has no owner. This assigns them
to one account.

Idempotent: re-running adopts nothing, and on a fresh database it adopts nothing
because there is nothing orphaned.

    SEED_USER_PASSWORD='…' uv run python -m scripts.seed_user

To change the password of an existing account, add --reset-password:

    SEED_USER_PASSWORD='…' uv run python -m scripts.seed_user --reset-password

The password is read from the environment and passed inline — nothing in this
project loads a .env file, so putting it there would produce a script that
always refuses to run.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text  # noqa: E402

from app.auth.passwords import hash_password  # noqa: E402
from app.database import SessionLocal, create_tables  # noqa: E402
from app.models import User  # noqa: E402

SEED_EMAIL = "bayo@superlearned.com"
MIN_PASSWORD_LENGTH = 8

# Every table that has no path to a Course and therefore cannot be attributed
# by joining. Courses cover everything else transitively.
ORPHAN_TABLES = ("courses", "user_events", "study_sessions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the first account and adopt orphaned data.")
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Set the password of an existing account to SEED_USER_PASSWORD.",
    )
    args = parser.parse_args()

    password = os.environ.get("SEED_USER_PASSWORD")
    if not password:
        print(
            "SEED_USER_PASSWORD is not set.\n\n"
            "  SEED_USER_PASSWORD='your-password' uv run python -m scripts.seed_user\n",
            file=sys.stderr,
        )
        return 1
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"SEED_USER_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 1

    # Safe to call repeatedly; ensures the users table and user_id columns exist
    # even if the app has never been started.
    create_tables()

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == SEED_EMAIL).first()
        if user is None:
            user = User(email=SEED_EMAIL, password_hash=hash_password(password))
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created user {SEED_EMAIL} ({user.id})")
        elif args.reset_password:
            user.password_hash = hash_password(password)
            db.commit()
            print(f"User {SEED_EMAIL} ({user.id}) — password updated")
        else:
            # Not changed silently: re-running the adoption step should never be
            # able to alter credentials as a side effect.
            print(
                f"User {SEED_EMAIL} already exists ({user.id}) — password unchanged.\n"
                "  To set a new password, re-run with --reset-password"
            )

        total = 0
        for table in ORPHAN_TABLES:
            try:
                result = db.execute(
                    text(f"UPDATE {table} SET user_id = :uid WHERE user_id IS NULL"),
                    {"uid": user.id},
                )
                db.commit()
                count = result.rowcount or 0
            except Exception as exc:
                # A fresh database may not have the raw-SQL tables yet.
                db.rollback()
                print(f"  {table:<16} skipped ({exc.__class__.__name__})")
                continue
            total += count
            print(f"  {table:<16} adopted {count} row(s)")

        print(f"\nDone. {total} row(s) now owned by {SEED_EMAIL}.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
