"""Auth endpoints: register, login, refresh, logout, me."""
from __future__ import annotations

from fastapi import APIRouter, status,Response

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.core.exceptions import InvalidCredentialsError
from app.core.security import hash_password, verify_password
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new organization with an owner user",
)
async def register(payload: RegisterRequest, db: DbSession) -> AuthResponse:
    service = AuthService(db)
    user, org = await service.register(payload)
    _, tokens = await service.authenticate(
        LoginRequest(email=payload.email, password=payload.password)
    )
    return AuthResponse(
        tokens=tokens,
        user=UserResponse.model_validate(user),
        organization=org,
    )


@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Authenticate with email + password",
)
async def login(payload: LoginRequest, db: DbSession) -> AuthResponse:
    from app.models.organization import Organization

    service = AuthService(db)
    user, tokens = await service.authenticate(payload)
    org = await db.get(Organization, user.organization_id)
    return AuthResponse(
        tokens=tokens,
        user=UserResponse.model_validate(user),
        organization=org,  # type: ignore[arg-type]
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    service = AuthService(db)
    return await service.refresh(payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    payload: RefreshRequest,
    db: DbSession,
) -> Response:
    service = AuthService(db)
    await service.logout(payload.refresh_token)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    # Validate current password
    if not verify_password(payload.current_password, user.hashed_password):
        raise InvalidCredentialsError("Current password is incorrect")

    # Validate new password rules
    if len(payload.new_password) < settings.PASSWORD_MIN_LENGTH:
        raise InvalidCredentialsError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters"
        )

    # Update password (IMPORTANT FIX)
    user.hashed_password = hash_password(payload.new_password)

    # Persist changes
    db.add(user)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
