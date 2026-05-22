# Authentication and user-management request/response schemas.

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.enums import UserRole
from app.schemas.common import ORMModel

# Registration
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    organization_name: str = Field(min_length=1, max_length=255)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < settings.PASSWORD_MIN_LENGTH:
            raise ValueError(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c.isalpha() for c in v):
            raise ValueError("Password must contain at least one letter")
        return v

# Login
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

# Token
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

# Refresh Token
class RefreshRequest(BaseModel):
    refresh_token: str

# User Response
class UserResponse(ORMModel):
    id: UUID
    email: EmailStr
    full_name: str
    role: UserRole
    organization_id: UUID
    is_active: bool
    is_verified: bool
    created_at: datetime

# Organization Response
class OrganizationResponse(ORMModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime

# Returned by /register and /login — token + user + org in one round-trip.
class AuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    tokens: TokenResponse
    user: UserResponse
    organization: OrganizationResponse

# Invite user
class InviteRequest(BaseModel):
    email: EmailStr
    role: UserRole = UserRole.VIEWER

# Accept User into Organization
class AcceptInviteRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)

# Change Password
class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)
