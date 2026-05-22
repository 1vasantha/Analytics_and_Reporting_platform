# API Key model for programmatic access (data ingestion endpoints).

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization

# Long-lived API key for ingestion endpoints.
class ApiKey(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_keys"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    hashed_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)

    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="api_keys")

    # Generate a new API key- (full_key, prefix, hashed)
    @staticmethod
    def generate() -> tuple[str, str, str]:
        random_part = secrets.token_urlsafe(32)
        prefix = secrets.token_hex(4)  # 8 hex chars
        full = f"ak_{prefix}_{random_part}"
        hashed = hashlib.sha256(full.encode()).hexdigest()
        return full, prefix, hashed

    @staticmethod
    def hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()
