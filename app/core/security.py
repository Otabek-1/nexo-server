from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import get_settings

pwd_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return pwd_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def _build_payload(sub: str, ttl: timedelta, token_type: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": sub,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    if extra:
        payload.update(extra)
    return payload


def create_access_token(user_id: UUID, email: str) -> str:
    settings = get_settings()
    payload = _build_payload(
        sub=str(user_id),
        ttl=timedelta(minutes=settings.jwt_access_ttl_min),
        token_type="access",
        extra={"email": email},
    )
    return jwt.encode(payload, settings.jwt_secret_key, algorithm="HS256")


def create_refresh_token(user_id: UUID) -> str:
    settings = get_settings()
    payload = _build_payload(
        sub=str(user_id),
        ttl=timedelta(days=settings.jwt_refresh_ttl_days),
        token_type="refresh",
    )
    return jwt.encode(payload, settings.jwt_refresh_secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=["HS256"])


def decode_refresh_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_refresh_secret_key, algorithms=["HS256"])

