"""Dashboard, widget, and metric query endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, status,Response

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import PermissionDeniedError
from app.models.enums import UserRole
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardResponse,
    DashboardSummaryResponse,
    DashboardUpdate,
    MetricQuery,
    MetricQueryResult,
    WidgetCreate,
    WidgetResponse,
    WidgetUpdate,
)
from app.services.dashboard_service import DashboardService
from app.services.metric_service import MetricService

router = APIRouter(prefix="/dashboards", tags=["dashboards"])


# ---------- Dashboards --------------------------------------------------


@router.get("", response_model=list[DashboardSummaryResponse])
async def list_dashboards(
    user: CurrentUser, db: DbSession
) -> list[DashboardSummaryResponse]:
    service = DashboardService(db)
    rows = await service.list_dashboards(user.organization_id)
    return [DashboardSummaryResponse.model_validate(r) for r in rows]


@router.post(
    "",
    response_model=DashboardResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_dashboard(
    payload: DashboardCreate,
    user: CurrentUser,
    db: DbSession,
) -> DashboardResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot create dashboards")
    service = DashboardService(db)
    dashboard = await service.create_dashboard(user.organization_id, user.id, payload)
    return DashboardResponse.model_validate(dashboard)


@router.get("/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(
    dashboard_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> DashboardResponse:
    service = DashboardService(db)
    dashboard = await service.get_dashboard(dashboard_id, user.organization_id)
    return DashboardResponse.model_validate(dashboard)


@router.patch("/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: uuid.UUID,
    payload: DashboardUpdate,
    user: CurrentUser,
    db: DbSession,
) -> DashboardResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit dashboards")
    service = DashboardService(db)
    dashboard = await service.update_dashboard(
        dashboard_id, user.organization_id, payload
    )
    return DashboardResponse.model_validate(dashboard)


@router.delete("/{dashboard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_dashboard(
    dashboard_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot delete dashboards")

    service = DashboardService(db)
    await service.delete_dashboard(dashboard_id, user.organization_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Widgets ------------------------------------------------------


@router.post(
    "/{dashboard_id}/widgets",
    response_model=WidgetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_widget(
    dashboard_id: uuid.UUID,
    payload: WidgetCreate,
    user: CurrentUser,
    db: DbSession,
) -> WidgetResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit dashboards")
    service = DashboardService(db)
    widget = await service.add_widget(dashboard_id, user.organization_id, payload)
    return WidgetResponse.model_validate(widget)


@router.patch("/widgets/{widget_id}", response_model=WidgetResponse)
async def update_widget(
    widget_id: uuid.UUID,
    payload: WidgetUpdate,
    user: CurrentUser,
    db: DbSession,
) -> WidgetResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit widgets")
    service = DashboardService(db)
    widget = await service.update_widget(widget_id, user.organization_id, payload)
    return WidgetResponse.model_validate(widget)


@router.delete("/widgets/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_widget(
    widget_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit widgets")

    service = DashboardService(db)
    await service.delete_widget(widget_id, user.organization_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)

# ---------- Ad-hoc metric query (no widget) -----------------------------


@router.post("/query", response_model=MetricQueryResult)
async def run_query(
    payload: MetricQuery, user: CurrentUser, db: DbSession
) -> MetricQueryResult:
    """Run an ad-hoc metric query.

    Used by the dashboard editor to preview a chart before saving.
    """
    service = MetricService(db)
    return await service.execute(user.organization_id, payload)


@router.get("/widgets/{widget_id}/data", response_model=MetricQueryResult)
async def get_widget_data(
    widget_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> MetricQueryResult:
    """Execute the saved query for a widget."""
    dash_service = DashboardService(db)
    widget = await dash_service._get_widget_for_org(widget_id, user.organization_id)
    query = MetricQuery.model_validate(widget.query_config)
    metric_service = MetricService(db)
    return await metric_service.execute(user.organization_id, query)
