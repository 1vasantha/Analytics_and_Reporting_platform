"""Security primitives: password hashing and JWT handling.

JWT tokens carry:
  - sub: user id
  - org: active organization id (for tenant isolation)
  - role: user's role in the org
  - type: "access" | "refresh"
  - exp/iat: standard JWT claims

Refresh tokens are stored in Redis with a JTI so they can be revoked.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app.core.config import settings

# bcrypt with reasonable cost (12 rounds ~= 250ms on modern hardware)
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)

TokenType = Literal["access", "refresh"]


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: str  # user_id (UUID string)
    org: str | None = None  # organization_id (UUID string)
    role: str | None = None
    type: TokenType
    jti: str
    exp: int
    iat: int


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return _pwd_context.verify(plain, hashed)
    except ValueError:
        # malformed hash
        return False


def _create_token(
    *,
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Create a signed JWT.

    Returns:
        Tuple of (encoded_token, jti). The jti can be persisted for revocation.
    """
    now = datetime.now(UTC)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    encoded = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded, jti


def create_access_token(
    user_id: str,
    *,
    org_id: str | None = None,
    role: str | None = None,
) -> tuple[str, str]:
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"org": org_id, "role": role},
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT.

    Raises:
        JWTError: If the token is invalid, expired, or malformed.
    """
    try:
        raw = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return TokenPayload(**raw)
    except (JWTError, ValueError) as exc:
        raise JWTError(f"Could not validate credentials: {exc}") from exc
