"""API Key model for programmatic access (data ingestion endpoints).

We store only the SHA256 hash of the secret part. The prefix (first 8 chars)
is stored in plaintext for identification in dashboards and logs.
"""
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


class ApiKey(UUIDMixin, TimestampMixin, Base):
    """Long-lived API key for ingestion endpoints."""

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

    @staticmethod
    def generate() -> tuple[str, str, str]:
        """Generate a new API key.

        Returns:
            (full_key, prefix, hashed) — `full_key` is shown to the user ONCE.
        """
        # Format: ak_<prefix>_<secret>  (e.g. ak_a3f9b7d2_<32-byte-base64>)
        random_part = secrets.token_urlsafe(32)
        prefix = secrets.token_hex(4)  # 8 hex chars
        full = f"ak_{prefix}_{random_part}"
        hashed = hashlib.sha256(full.encode()).hexdigest()
        return full, prefix, hashed

    @staticmethod
    def hash_key(key: str) -> str:
        return hashlib.sha256(key.encode()).hexdigest()
