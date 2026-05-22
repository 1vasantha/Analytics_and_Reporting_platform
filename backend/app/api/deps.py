"""FastAPI dependencies for authentication and authorization.

Usage in endpoints:
    @router.get("/me")
    async def me(user: CurrentUser) -> UserResponse: ...

    @router.delete("/dashboards/{id}", dependencies=[require_role(UserRole.ADMIN)])
    async def delete(...) -> None: ...
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthenticationError,
    PermissionDeniedError,
    TokenExpiredError,
)
from app.core.security import decode_token
from app.db.session import get_db
from app.models.api_key import ApiKey
from app.models.enums import UserRole
from app.models.user import User
from sqlalchemy import select

# tokenUrl is for OpenAPI docs only; actual login is JSON
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    db: DbSession,
    token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> User:
    """Validate the bearer token and return the User.

    Raises:
        AuthenticationError: If no token or invalid token.
        TokenExpiredError: If token is expired.
    """
    if not token:
        raise AuthenticationError("Not authenticated")

    try:
        payload = decode_token(token)
    except JWTError as exc:
        raise TokenExpiredError(str(exc)) from exc

    if payload.type != "access":
        raise AuthenticationError("Wrong token type")

    user = await db.get(User, uuid.UUID(payload.sub))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed: UserRole):
    """Dependency factory: enforce that current user has one of the given roles."""

    async def _check(user: CurrentUser) -> User:
        if user.role not in [r.value for r in allowed]:
            raise PermissionDeniedError(
                f"Requires one of: {', '.join(r.value for r in allowed)}"
            )
        return user

    return Depends(_check)


# ----- API Key auth (for ingestion endpoints) ----------------------------


async def get_api_key(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiKey:
    """Authenticate via API key from either `Authorization: Bearer <key>` or `X-API-Key`."""
    raw_key: str | None = x_api_key
    if not raw_key and authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer":
            raw_key = value.strip()

    if not raw_key:
        raise AuthenticationError("API key required")

    hashed = ApiKey.hash_key(raw_key)
    api_key = await db.scalar(
        select(ApiKey).where(ApiKey.hashed_key == hashed, ApiKey.revoked.is_(False))
    )
    if not api_key:
        raise AuthenticationError("Invalid API key")

    return api_key


ApiKeyAuth = Annotated[ApiKey, Depends(get_api_key)]
