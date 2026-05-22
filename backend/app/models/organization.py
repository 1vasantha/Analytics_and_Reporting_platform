"""Organization (tenant) model.

Every other domain entity (users, events, dashboards, alerts) belongs to
exactly one organization. All queries MUST filter by organization_id.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.dashboard import Dashboard
    from app.models.event import Event
    from app.models.user import User


class Organization(UUIDMixin, TimestampMixin, Base):
    """A tenant in the multi-tenant system."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # Relationships
    users: Mapped[list["User"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    dashboards: Mapped[list["Dashboard"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Organization {self.slug}>"


class Invitation(UUIDMixin, TimestampMixin, Base):
    """Pending invitations to join an organization."""

    __tablename__ = "invitations"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    invited_by_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    accepted_at: Mapped[str | None] = mapped_column(String, nullable=True)
