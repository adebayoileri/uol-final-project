"""Password hashing.

Uses stdlib `hashlib.scrypt` rather than bcrypt or argon2. Both are stronger
choices in production, but each needs a compiled wheel; scrypt is memory-hard,
in the standard library, and adds no dependency to install or fail. The stored
format encodes its own parameters so a rehash-on-login upgrade stays open.
"""

import base64
import hashlib
import hmac
import secrets

# OWASP's stated floor for scrypt. ~40ms per hash on the target machine.
_N = 2**14
_R = 8
_P = 1
_DKLEN = 32
_SALT_BYTES = 16
# 128 * N * r = 16 MiB at these parameters. OpenSSL's default cap is 32 MB, so
# raising _N without raising this produces an opaque "memory limit exceeded".
_MAXMEM = 64 * 1024 * 1024

_PREFIX = "scrypt"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=n,
        r=r,
        p=p,
        dklen=_DKLEN,
        maxmem=_MAXMEM,
    )


def hash_password(password: str) -> str:
    """Return a self-describing `scrypt$n$r$p$salt$hash` string."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = _derive(password, salt, _N, _R, _P)
    return f"{_PREFIX}${_N}${_R}${_P}${_b64(salt)}${_b64(derived)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check. Returns False on a malformed stored hash.

    Never raises: a truncated or corrupted column value must fail the login,
    not 500 the route.
    """
    if not stored:
        return False
    try:
        prefix, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$")
        if prefix != _PREFIX:
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        derived = _derive(password, salt, int(n_s), int(r_s), int(p_s))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derived, expected)


# Verified on import so an unknown email costs the same as a wrong password.
# Without this, login timing distinguishes "no such account" from "bad password".
DUMMY_HASH = hash_password("dummy-password-for-timing-equalisation")
