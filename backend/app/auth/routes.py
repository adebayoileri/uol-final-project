"""Registration, login, logout and identity.

This router is registered WITHOUT the auth dependency — see app/main.py.
"""

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.auth.passwords import DUMMY_HASH, hash_password, verify_password
from app.auth.sessions import (
    COOKIE_NAME,
    clear_session_cookie,
    create_session,
    revoke_session,
    set_session_cookie,
)
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

# Deliberately permissive: enough to reject obvious typos without pulling in
# email-validator as a dependency for a local single-machine app.
_EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class Credentials(BaseModel):
    email: str = Field(..., min_length=3, max_length=255, pattern=_EMAIL_PATTERN)
    # The maximum matters as much as the minimum: without it a multi-megabyte
    # password is a free 16 MiB-per-attempt hashing DoS.
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value):
        """Normalise BEFORE the pattern runs.

        The pattern excludes whitespace, so a pasted address with a trailing
        space would otherwise be rejected as malformed rather than accepted and
        trimmed. Doing it here also guarantees the stored value and the value
        the UNIQUE constraint sees are the same.
        """
        return value.strip().lower() if isinstance(value, str) else value


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str


def _normalise(email: str) -> str:
    return email.strip().lower()


@router.post("/register", response_model=UserResponse, status_code=201)
def register(body: Credentials, response: Response, db: Session = Depends(get_db)):
    email = _normalise(body.email)

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with that email already exists.")

    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    set_session_cookie(response, create_session(db, user))
    return user


@router.post("/login", response_model=UserResponse)
def login(body: Credentials, response: Response, db: Session = Depends(get_db)):
    email = _normalise(body.email)
    user = db.query(User).filter(User.email == email).first()

    # Verify against a dummy hash when the account doesn't exist, so an unknown
    # email costs the same as a wrong password and the two are indistinguishable
    # by timing. The response is byte-identical in both cases.
    if user is None:
        verify_password(body.password, DUMMY_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    set_session_cookie(response, create_session(db, user))
    return user


@router.post("/logout", status_code=204)
def logout(
    response: Response,
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: Session = Depends(get_db),
):
    """Deliberately does NOT require auth.

    An expired or already-revoked session must still be able to clear its
    cookie, otherwise the user is stuck on a login page that immediately 401s.
    """
    if session:
        revoke_session(db, session)
    clear_session_cookie(response)
    return None


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(current_user)):
    return user
