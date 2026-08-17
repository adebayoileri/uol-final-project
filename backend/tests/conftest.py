"""Shared test setup.

Every test file builds its own engine and `client` fixture. Rather than editing
sixteen of them, this autouse fixture overrides the auth dependency globally —
`app.dependency_overrides` lives on the app object, so it reaches those local
fixtures without touching them.
"""

from types import SimpleNamespace

import pytest

from app.auth.deps import current_user
from app.main import app

# A stand-in rather than a real row: the routes only ever read `.id`, and this
# keeps tests independent of the users table existing in their schema.
TEST_USER_ID = "test-user-0000"
TEST_USER = SimpleNamespace(id=TEST_USER_ID, email="test@example.com")


@pytest.fixture(autouse=True)
def bypass_auth():
    app.dependency_overrides[current_user] = lambda: TEST_USER
    yield
    # .pop rather than del: the per-file client fixtures call
    # dependency_overrides.clear() on teardown and may have removed it already.
    app.dependency_overrides.pop(current_user, None)
