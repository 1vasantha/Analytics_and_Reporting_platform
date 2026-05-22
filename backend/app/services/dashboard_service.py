"""Dashboard and widget service."""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.logging import get_logger
from app.models.dashboard import Dashboard, Widget
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardUpdate,
    WidgetCreate,
    WidgetUpdate,
)

log = get_logger(__name__)


class DashboardService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------- Dashboards ----------------------------------------------

    async def list_dashboards(self, organization_id: uuid.UUID) -> list[Dashboard]:
        result = await self.db.execute(
            select(Dashboard)
            .where(Dashboard.organization_id == organization_id)
            .order_by(Dashboard.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_dashboard(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Dashboard:
        stmt = (
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(
                Dashboard.id == dashboard_id,
                Dashboard.organization_id == organization_id,
            )
        )
        dashboard = await self.db.scalar(stmt)
        if not dashboard:
            raise NotFoundError("Dashboard not found")
        return dashboard

    async def get_by_share_token(self, token: str) -> Dashboard:
        stmt = (
            select(Dashboard)
            .options(selectinload(Dashboard.widgets))
            .where(Dashboard.share_token == token, Dashboard.is_public.is_(True))
        )
        dashboard = await self.db.scalar(stmt)
        if not dashboard:
            raise NotFoundError("Public dashboard not found")
        return dashboard

    async def create_dashboard(
        self,
        organization_id: uuid.UUID,
        created_by_id: uuid.UUID,
        payload: DashboardCreate,
    ) -> Dashboard:
        dashboard = Dashboard(
            organization_id=organization_id,
            created_by_id=created_by_id,
            name=payload.name,
            description=payload.description,
            refresh_interval=payload.refresh_interval,
            is_public=payload.is_public,
            share_token=secrets.token_urlsafe(24) if payload.is_public else None,
        )
        self.db.add(dashboard)
        await self.db.commit()
        await self.db.refresh(dashboard, ["widgets"])
        return dashboard

    async def update_dashboard(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: DashboardUpdate,
    ) -> Dashboard:
        dashboard = await self.get_dashboard(dashboard_id, organization_id)

        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(dashboard, key, value)

        # If toggling public on/off, regenerate share token
        if "is_public" in data:
            dashboard.share_token = secrets.token_urlsafe(24) if data["is_public"] else None

        await self.db.commit()
        await self.db.refresh(dashboard, ["widgets"])
        return dashboard

    async def delete_dashboard(
        self, dashboard_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        dashboard = await self.get_dashboard(dashboard_id, organization_id)
        await self.db.delete(dashboard)
        await self.db.commit()

    # ---------- Widgets -------------------------------------------------

    async def add_widget(
        self,
        dashboard_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: WidgetCreate,
    ) -> Widget:
        # Ensure dashboard belongs to org (and exists)
        await self.get_dashboard(dashboard_id, organization_id)

        widget = Widget(
            dashboard_id=dashboard_id,
            title=payload.title,
            chart_type=payload.chart_type,
            query_config=payload.query_config.model_dump(mode="json"),
            layout=payload.layout.model_dump(),
            position=payload.position,
        )
        self.db.add(widget)
        await self.db.commit()
        await self.db.refresh(widget)
        return widget

    async def update_widget(
        self,
        widget_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: WidgetUpdate,
    ) -> Widget:
        widget = await self._get_widget_for_org(widget_id, organization_id)
        data = payload.model_dump(exclude_unset=True, mode="json")
        for key, value in data.items():
            setattr(widget, key, value)
        await self.db.commit()
        await self.db.refresh(widget)
        return widget

    async def delete_widget(
        self, widget_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        widget = await self._get_widget_for_org(widget_id, organization_id)
        await self.db.delete(widget)
        await self.db.commit()

    async def _get_widget_for_org(
        self, widget_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Widget:
        stmt = (
            select(Widget)
            .join(Dashboard)
            .where(
                Widget.id == widget_id,
                Dashboard.organization_id == organization_id,
            )
        )
        widget = await self.db.scalar(stmt)
        if not widget:
            raise NotFoundError("Widget not found")
        return widget
