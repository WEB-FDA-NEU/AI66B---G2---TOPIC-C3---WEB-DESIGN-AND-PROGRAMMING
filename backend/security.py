"""Argon2id passwords and revocable JWT sessions. No raw token storage/logging."""

import hashlib
import secrets
from datetime import timedelta

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .models import AuthSession, utcnow

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


def hash_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ValueError("Password must contain 8-128 characters")
    try:
        password.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("Password must be valid UTF-8") from None
    return hasher.hash(password)


def verify_password(password, hashed):
    if not isinstance(password, str) or not 1 <= len(password) <= 128:
        return False
    try:
        if hashed.startswith(("$2a$", "$2b$", "$2y$")):
            # Legacy hashes were truncated by the old template. Never repeat that behavior.
            raw = password.encode("utf-8")
            return len(raw) <= 72 and bcrypt.checkpw(raw, hashed.encode("ascii"))
        return hasher.verify(hashed, password)
    except (VerificationError, InvalidHashError, ValueError, TypeError):
        return False


def session_id(jti):
    return hashlib.sha256(jti.encode()).hexdigest()


def issue_token(db, user, settings):
    now = utcnow()
    expiry = now + timedelta(minutes=settings.jwt_expire_minutes)
    jti = secrets.token_urlsafe(32)
    db.add(AuthSession(id=session_id(jti), user_id=user.id, expires_at=expiry))
    token = jwt.encode(
        {
            "sub": str(user.id),
            "ver": user.token_version,
            "jti": jti,
            "iat": now,
            "nbf": now,
            "exp": expiry,
            "iss": "luxstay",
            "aud": "luxstay-api",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    return token


def decode_token(token, settings):
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer="luxstay",
            audience="luxstay-api",
            options={"require": ["sub", "ver", "jti", "exp", "iat", "nbf", "iss", "aud"]},
            leeway=2,
        )
        if (
            not isinstance(claims["sub"], str)
            or not claims["sub"].isdigit()
            or not isinstance(claims["ver"], int)
            or not isinstance(claims["jti"], str)
        ):
            return None
        return claims
    except jwt.PyJWTError:
        return None
