"""Every route must require authentication.

This is a stronger claim than enumerating the routes that are protected today:
it fails for any route added later without a gate, including ones written after
this audit.
"""

from fastapi.routing import APIRoute

from app.auth.deps import current_user
from app.main import app

# Deliberately public. `/` and `/health` are liveness checks; the OpenAPI routes
# describe the surface; the auth routes must be reachable without a session, and
# logout must work even with an expired one.
EXEMPT_PATHS = {
    "/",
    "/health",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
    "/auth/register",
    "/auth/login",
    "/auth/logout",
}


def _dependency_calls(dependant) -> set:
    """Every callable in a route's dependency tree, at any depth."""
    found = {dependant.call} if dependant.call else set()
    for sub in dependant.dependencies:
        found |= _dependency_calls(sub)
    return found


def _guarded_routes():
    return [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path not in EXEMPT_PATHS
    ]


def test_every_route_requires_authentication():
    unprotected = [
        f"{sorted(route.methods)} {route.path}"
        for route in _guarded_routes()
        if current_user not in _dependency_calls(route.dependant)
    ]
    assert not unprotected, "Unprotected routes:\n  " + "\n  ".join(unprotected)


def test_the_guarded_set_is_not_empty():
    """Guards the guard: a refactor that stopped collecting routes would
    otherwise make the test above pass vacuously."""
    assert len(_guarded_routes()) > 20


def test_public_routes_are_actually_reachable_without_auth():
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        assert c.get("/health").status_code == 200
        assert c.get("/").status_code == 200
