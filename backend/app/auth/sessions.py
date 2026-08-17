"""Server-side login sessions."""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AuthSession, User

COOKIE_NAME = "session"
SESSION_DAYS = 14
COOKIE_MAX_AGE = SESSION_DAYS * 24 * 60 * 60


def create_session(db: Session, user: User) -> str:
    """Issue a new session and return its opaque token.

    A fresh row per login rather than reusing one, so a stolen cookie is
    invalidated by the next sign-in and the table doubles as a login audit.
    """
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            id=token,
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS),
            revoked=0,
        )
    )
    db.commit()
    return token


def resolve_session(db: Session, token: str) -> User | None:
    """Return the owning user, or None if the token is unknown, revoked or expired."""
    if not token:
        return None

    row = db.get(AuthSession, token)
    if row is None or row.revoked:
        return None

    expires = row.expires_at
    # SQLite hands back naive datetimes; compare in UTC either way.
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= datetime.now(timezone.utc):
        return None

    return db.get(User, row.user_id)


def revoke_session(db: Session, token: str) -> None:
    """Best-effort revoke. Logging out with a dead token must still succeed."""
    if not token:
        return
    row = db.get(AuthSession, token)
    if row is not None and not row.revoked:
        row.revoked = 1
        db.commit()


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        # Mandatory on http://localhost — a Secure cookie is silently dropped
        # over plain HTTP. A cross-host deployment needs samesite="none" and
        # secure=True together.
        secure=False,
        path="/",
        max_age=COOKIE_MAX_AGE,
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(key=COOKIE_NAME, path="/")
