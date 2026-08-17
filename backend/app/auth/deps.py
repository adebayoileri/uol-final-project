"""The single auth dependency.

`current_user` both gates (raises 401) and supplies the user. FastAPI caches
sub-dependency results per request, so declaring it on a router AND in a
handler signature resolves once and hits the database once — and tests get a
single override key.
"""

from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.sessions import COOKIE_NAME, resolve_session
from app.database import get_db
from app.models import User


def current_user(
    # Declared as Cookie(...) rather than read off Request so it appears in the
    # OpenAPI schema and /docs stays usable.
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    if not session:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    user = resolve_session(db, session)
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return user
