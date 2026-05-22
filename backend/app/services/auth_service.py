# Authentication service- Register a new organization + owner user, Authenticate users, Refresh access, Logout

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ConflictError,
    InvalidCredentialsError,
    TokenExpiredError,
)
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.redis import get_redis
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse

log = get_logger(__name__)

# Lowercase, hyphenate, strip non-alphanumeric
def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:48] or "org"

# Encapsulates all authentication operations
class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Registration
    async def register(self, payload: RegisterRequest) -> tuple[User, Organization]:
        existing = await self.db.scalar(select(User).where(User.email == payload.email))
        if existing:
            raise ConflictError("A user with this email already exists")

        slug_base = _slugify(payload.organization_name)
        slug = await self._unique_slug(slug_base)

        org = Organization(name=payload.organization_name, slug=slug)
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            hashed_password=hash_password(payload.password),
            organization=org,
            role=UserRole.OWNER,
            is_active=True,
            is_verified=False,
        )

        self.db.add(org)
        self.db.add(user)

        try:
            await self.db.commit()
        except IntegrityError as exc:
            await self.db.rollback()
            log.warning("auth.register.integrity_error", error=str(exc))
            raise ConflictError("Email or organization already exists") from exc

        await self.db.refresh(user)
        await self.db.refresh(org)
        log.info("auth.registered", user_id=str(user.id), org_id=str(org.id))
        return user, org

    async def _unique_slug(self, base: str) -> str:
        """Find an unused org slug, appending -2, -3, etc. if needed."""
        slug = base
        for suffix in range(2, 100):
            existing = await self.db.scalar(
                select(Organization.id).where(Organization.slug == slug)
            )
            if not existing:
                return slug
            slug = f"{base}-{suffix}"
        return f"{base}-{uuid.uuid4().hex[:6]}"

    # Login
    async def authenticate(self, payload: LoginRequest) -> tuple[User, TokenResponse]:
        user = await self.db.scalar(select(User).where(User.email == payload.email))

        valid_password = verify_password(
            payload.password,
            user.hashed_password if user else "$2b$12$.invalid.hash.placeholder.................",
        )

        if not user or not valid_password:
            log.info("auth.login.failed", email=payload.email)
            raise InvalidCredentialsError()

        if not user.is_active:
            log.info("auth.login.inactive", user_id=str(user.id))
            raise InvalidCredentialsError("Account is disabled")

        tokens = await self._issue_tokens(user)
        log.info("auth.login.success", user_id=str(user.id))
        return user, tokens

    # Token issuing & refresh
    async def _issue_tokens(self, user: User) -> TokenResponse:
        access_token, _ = create_access_token(
            str(user.id), org_id=str(user.organization_id), role=user.role
        )
        refresh_token, refresh_jti = create_refresh_token(str(user.id))

        redis = get_redis()
        ttl = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600
        await redis.set(f"refresh:{refresh_jti}", str(user.id), ex=ttl)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    # Issue a new access token (and rotate refresh token) given a refresh token
    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except JWTError as exc:
            raise TokenExpiredError(str(exc)) from exc

        if payload.type != "refresh":
            raise InvalidCredentialsError("Token is not a refresh token")

        redis = get_redis()
        stored = await redis.get(f"refresh:{payload.jti}")
        if not stored:
            raise TokenExpiredError("Refresh token has been revoked")

        if stored != payload.sub:
            raise InvalidCredentialsError("Refresh token user mismatch")

        await redis.delete(f"refresh:{payload.jti}")

        user = await self.db.get(User, uuid.UUID(payload.sub))
        if not user or not user.is_active:
            raise InvalidCredentialsError()

        return await self._issue_tokens(user)

    # Revoke a refresh token. Best-effort: ignores invalid tokens
    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
            redis = get_redis()
            await redis.delete(f"refresh:{payload.jti}")
        except JWTError:
            pass 
