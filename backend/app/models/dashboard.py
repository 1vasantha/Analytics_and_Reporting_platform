# Dashboard and Widget models- Widget-saved query config (metric, aggregation, filters, time range, granularity) plus presentation (chart type, layout position).

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization

# A dashboard — collection of widgets with a layout.
class Dashboard(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "dashboards"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    share_token: Mapped[str | None] = mapped_column(
        String(128), unique=True, nullable=True, index=True
    )

    refresh_interval: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="dashboards", lazy="selectin")
    widgets: Mapped[list["Widget"]] = relationship(
        back_populates="dashboard",
        cascade="all, delete-orphan",
        order_by="Widget.position", lazy="selectin"
    )

# A single chart on a dashboard- `query_config` is a JSON blob whose schema is validated by Pydantic
class Widget(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "widgets"

    dashboard_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dashboards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    chart_type: Mapped[str] = mapped_column(String(32), nullable=False)
    query_config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    layout: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=lambda: {"x": 0, "y": 0, "w": 6, "h": 4}
    )

    dashboard: Mapped["Dashboard"] = relationship(back_populates="widgets")
