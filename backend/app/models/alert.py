"""Alert and Notification models.

Alerts run on a Celery Beat schedule. Each alert evaluates a metric query
against a threshold and, if breached, creates a Notification through one or
more channels (email, in-app, webhook).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Alert(UUIDMixin, TimestampMixin, Base):
    """A threshold-based alert configuration."""

    __tablename__ = "alerts"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Query config (same shape as Widget.query_config)
    query_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # Threshold
    operator: Mapped[str] = mapped_column(String(8), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)

    # Evaluation cadence in seconds (e.g. 60 = check every minute)
    check_interval_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)

    # Cooldown so we don't spam: don't refire within this many seconds
    cooldown_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)

    # Channels: list of strings e.g. ["email", "in_app", "webhook"]
    channels: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    # Per-channel config (email recipients, webhook URL, etc.)
    channel_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    # State
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class Notification(UUIDMixin, Base):
    """A notification emitted by an alert firing.

    Used to populate the in-app notification feed and for audit/history.
    """

    __tablename__ = "notifications"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")

    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )


class ScheduledReport(UUIDMixin, TimestampMixin, Base):
    """A scheduled report — emails a dashboard snapshot to recipients."""

    __tablename__ = "scheduled_reports"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    recipients: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
