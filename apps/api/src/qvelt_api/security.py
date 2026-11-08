"""Argon2id passwords and digest-only storage of opaque session tokens."""
import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

password_hasher = PasswordHasher()
# Missing users still incur a real password verification.
dummy_hash = password_hasher.hash(secrets.token_urlsafe(32))
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


def verify_password(encoded: str, password: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except VerificationError:
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()
