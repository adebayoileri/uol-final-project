"""Registration, login, logout and session lifecycle.

These use the REAL auth dependency, so the autouse bypass in conftest is
disabled per-test — otherwise every request would be pre-authenticated and the
tests would prove nothing.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.deps import current_user
from app.auth.passwords import hash_password, verify_password
from app.database import Base, get_db
from app.main import app
from app.models import AuthSession, User


@pytest.fixture()
def test_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(test_engine):
    db = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(test_engine, bypass_auth):
    """Real auth: drop the autouse override so 401s actually happen."""
    app.dependency_overrides.pop(current_user, None)

    TestingSession = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


CREDS = {"email": "bayo@superlearned.com", "password": "correct-horse-battery", "name": "Bayo"}


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def test_register_creates_account_and_signs_in(client):
    resp = client.post("/auth/register", json=CREDS)
    assert resp.status_code == 201
    assert resp.json()["email"] == "bayo@superlearned.com"
    # Registration signs you in, so /me works immediately.
    assert client.get("/auth/me").status_code == 200


# ---------------------------------------------------------------------------
# Display name. The split of RegisterRequest from Credentials is what keeps
# login's contract unchanged, so the test that proves it matters most is the
# one asserting login still works with no name in the body.
# ---------------------------------------------------------------------------

def test_login_does_not_require_a_name(client):
    """`name` is register-only. On Credentials it would break every client."""
    client.post("/auth/register", json=CREDS)
    res = client.post(
        "/auth/login",
        json={"email": CREDS["email"], "password": CREDS["password"]},
    )
    assert res.status_code == 200


def test_registration_requires_a_name(client):
    res = client.post(
        "/auth/register",
        json={"email": CREDS["email"], "password": CREDS["password"]},
    )
    assert res.status_code == 422


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_unusable_names_are_rejected(client, name):
    assert client.post("/auth/register", json={**CREDS, "name": name}).status_code == 422


def test_name_is_stored_and_returned(client, db_session):
    res = client.post("/auth/register", json={**CREDS, "name": "  Ada Lovelace  "})
    assert res.status_code == 201
    assert res.json()["name"] == "Ada Lovelace"
    assert db_session.query(User).one().name == "Ada Lovelace"


def test_me_reports_the_name(client):
    client.post("/auth/register", json={**CREDS, "name": "Ada"})
    assert client.get("/auth/me").json()["name"] == "Ada"


def test_a_legacy_account_without_a_name_still_resolves(client, db_session):
    """Rows predating the column must keep working, name reported as null."""
    client.post("/auth/register", json=CREDS)
    db_session.query(User).one().name = None
    db_session.commit()

    body = client.get("/auth/me").json()
    assert body["name"] is None
    assert body["email"] == CREDS["email"]


def test_register_sets_an_httponly_cookie(client):
    resp = client.post("/auth/register", json=CREDS)
    # The cookie jar hides flags, so assert on the raw header.
    set_cookie = resp.headers["set-cookie"]
    assert "session=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie


@pytest.mark.parametrize(
    "variant",
    ["bayo@superlearned.com", "BAYO@Superlearned.com", "  bayo@superlearned.com  "],
)
def test_duplicate_email_is_rejected_regardless_of_case_or_whitespace(client, variant):
    assert client.post("/auth/register", json=CREDS).status_code == 201
    dupe = client.post("/auth/register", json={**CREDS, "email": variant})
    assert dupe.status_code == 409


def test_email_is_stored_normalised(client, db_session):
    client.post("/auth/register", json={**CREDS, "email": "  BAYO@Superlearned.COM "})
    assert db_session.query(User).one().email == "bayo@superlearned.com"


@pytest.mark.parametrize("password", ["short", "", "a" * 129])
def test_password_length_is_enforced(client, password):
    resp = client.post("/auth/register", json={**CREDS, "password": password})
    assert resp.status_code == 422


@pytest.mark.parametrize("email", ["not-an-email", "no@tld", "@nolocal.com", "a b@c.com"])
def test_malformed_email_is_rejected(client, email):
    assert client.post("/auth/register", json={**CREDS, "email": email}).status_code == 422


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def test_login_succeeds_with_correct_password(client):
    client.post("/auth/register", json=CREDS)
    client.post("/auth/logout")
    assert client.post("/auth/login", json=CREDS).status_code == 200
    assert client.get("/auth/me").json()["email"] == "bayo@superlearned.com"


def test_login_accepts_a_differently_cased_email(client):
    client.post("/auth/register", json=CREDS)
    client.post("/auth/logout")
    resp = client.post("/auth/login", json={**CREDS, "email": "BAYO@SUPERLEARNED.COM"})
    assert resp.status_code == 200


def test_wrong_password_and_unknown_email_are_indistinguishable(client):
    """No oracle telling an attacker which accounts exist."""
    client.post("/auth/register", json=CREDS)
    client.post("/auth/logout")

    wrong_password = client.post("/auth/login", json={**CREDS, "password": "wrong-password-x"})
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@nowhere.com", "password": "wrong-password-x"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()


def test_login_issues_a_new_session_each_time(client, db_session):
    client.post("/auth/register", json=CREDS)
    client.post("/auth/logout")
    client.post("/auth/login", json=CREDS)
    client.post("/auth/logout")
    client.post("/auth/login", json=CREDS)
    # register + 2 logins
    assert db_session.query(AuthSession).count() == 3


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------

def test_me_requires_a_session(client):
    assert client.get("/auth/me").status_code == 401


def test_logout_revokes_the_session(client):
    client.post("/auth/register", json=CREDS)
    assert client.post("/auth/logout").status_code == 204
    assert client.get("/auth/me").status_code == 401


def test_logout_without_a_session_still_succeeds(client):
    """An expired cookie must be clearable, or the user is stuck at the login page."""
    assert client.post("/auth/logout").status_code == 204


def test_expired_session_is_rejected(client, db_session):
    client.post("/auth/register", json=CREDS)
    row = db_session.query(AuthSession).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db_session.commit()
    assert client.get("/auth/me").status_code == 401


def test_revoked_session_is_rejected(client, db_session):
    client.post("/auth/register", json=CREDS)
    row = db_session.query(AuthSession).one()
    row.revoked = 1
    db_session.commit()
    assert client.get("/auth/me").status_code == 401


def test_unknown_session_token_is_rejected(client):
    client.cookies.set("session", "not-a-real-token")
    assert client.get("/auth/me").status_code == 401


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def test_password_roundtrip():
    stored = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", stored)
    assert not verify_password("wrong", stored)


def test_same_password_hashes_differently():
    """Per-hash salt, so identical passwords don't share a digest."""
    assert hash_password("same") != hash_password("same")


def test_hash_records_its_parameters():
    stored = hash_password("x")
    assert stored.startswith("scrypt$16384$8$1$")
    assert len(stored.split("$")) == 6


@pytest.mark.parametrize("stored", ["", "garbage", "scrypt$bad", "bcrypt$1$2$3$a$b", "scrypt$a$b$c$!$!"])
def test_malformed_stored_hash_returns_false_rather_than_raising(stored):
    """A corrupted column must fail the login, not 500 the route."""
    assert verify_password("anything", stored) is False
