"""Event model — the time-series fact table.
Indexed for the common query patterns:
- Filter by org + event_name + time range (most aggregations)
- Filter by org + source + time range
- JSONB properties allow arbitrary flexible attributes per event
For production scale this table should be partitioned by month (declarative
partitioning is created by the Alembic migration).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization

# A single observed event/data point.
class Event(UUIDMixin, Base):
    __tablename__ = "events"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )

    event_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, default="api")

    user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)

    value: Mapped[float | None] = mapped_column(Float, nullable=True)

    properties: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(),
    )

    organization: Mapped["Organization"] = relationship(back_populates="events")

    __table_args__ = (
        Index("ix_events_org_name_time", "organization_id", "event_name", "occurred_at"),
        Index("ix_events_org_source_time", "organization_id", "source", "occurred_at"),
        Index("ix_events_org_time", "organization_id", "occurred_at"),
        Index("ix_events_properties_gin", "properties", postgresql_using="gin"),
    )

# Tracks async CSV-upload ingestion jobs.
class IngestionJob(UUIDMixin, Base):
    __tablename__ = "ingestion_jobs"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    total_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    processed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    failed_rows: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
