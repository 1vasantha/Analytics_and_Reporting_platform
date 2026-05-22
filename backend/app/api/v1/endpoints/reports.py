"""Scheduled report management endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, status,Response
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.models.alert import ScheduledReport
from app.models.dashboard import Dashboard
from app.models.enums import ReportFrequency, UserRole
from app.schemas.alert import (
    ScheduledReportCreate,
    ScheduledReportResponse,
    ScheduledReportUpdate,
)

router = APIRouter(prefix="/reports", tags=["reports"])


def _compute_next_run(frequency: ReportFrequency, now: datetime | None = None) -> datetime:
    now = now or datetime.now(UTC)
    if frequency == ReportFrequency.DAILY:
        return now + timedelta(days=1)
    if frequency == ReportFrequency.WEEKLY:
        return now + timedelta(weeks=1)
    return now + timedelta(days=30)


@router.get("", response_model=list[ScheduledReportResponse])
async def list_reports(
    user: CurrentUser, db: DbSession
) -> list[ScheduledReportResponse]:
    result = await db.execute(
        select(ScheduledReport)
        .where(ScheduledReport.organization_id == user.organization_id)
        .order_by(ScheduledReport.created_at.desc())
    )
    return [ScheduledReportResponse.model_validate(r) for r in result.scalars()]


@router.post(
    "",
    response_model=ScheduledReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_report(
    payload: ScheduledReportCreate, user: CurrentUser, db: DbSession
) -> ScheduledReportResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot create reports")

    # Verify the dashboard belongs to the user's org
    dashboard = await db.scalar(
        select(Dashboard).where(
            Dashboard.id == payload.dashboard_id,
            Dashboard.organization_id == user.organization_id,
        )
    )
    if not dashboard:
        raise NotFoundError("Dashboard not found")

    report = ScheduledReport(
        organization_id=user.organization_id,
        dashboard_id=payload.dashboard_id,
        created_by_id=user.id,
        name=payload.name,
        frequency=payload.frequency,
        recipients=list(payload.recipients),
        is_enabled=payload.is_enabled,
        next_run_at=_compute_next_run(payload.frequency),
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return ScheduledReportResponse.model_validate(report)


@router.patch("/{report_id}", response_model=ScheduledReportResponse)
async def update_report(
    report_id: uuid.UUID,
    payload: ScheduledReportUpdate,
    user: CurrentUser,
    db: DbSession,
) -> ScheduledReportResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit reports")

    report = await db.scalar(
        select(ScheduledReport).where(
            ScheduledReport.id == report_id,
            ScheduledReport.organization_id == user.organization_id,
        )
    )
    if not report:
        raise NotFoundError("Report not found")

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(report, key, value)
    if "frequency" in data:
        report.next_run_at = _compute_next_run(ReportFrequency(report.frequency))

    await db.commit()
    await db.refresh(report)
    return ScheduledReportResponse.model_validate(report)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot delete reports")

    report = await db.scalar(
        select(ScheduledReport).where(
            ScheduledReport.id == report_id,
            ScheduledReport.organization_id == user.organization_id,
        )
    )

    if not report:
        raise NotFoundError("Report not found")

    await db.delete(report)
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
