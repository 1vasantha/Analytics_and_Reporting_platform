"""Alert and notification endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Query, status,Response
from sqlalchemy import func, select, update

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import PermissionDeniedError
from app.models.alert import Notification
from app.models.enums import UserRole
from app.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertUpdate,
    NotificationResponse,
)
from app.services.alert_service import AlertService

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertResponse])
async def list_alerts(user: CurrentUser, db: DbSession) -> list[AlertResponse]:
    service = AlertService(db)
    return [
        AlertResponse.model_validate(a)
        for a in await service.list_alerts(user.organization_id)
    ]


@router.post(
    "",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_alert(
    payload: AlertCreate, user: CurrentUser, db: DbSession
) -> AlertResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot create alerts")
    service = AlertService(db)
    alert = await service.create_alert(user.organization_id, user.id, payload)
    return AlertResponse.model_validate(alert)


@router.get("/{alert_id}", response_model=AlertResponse)
async def get_alert(
    alert_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> AlertResponse:
    service = AlertService(db)
    alert = await service.get_alert(alert_id, user.organization_id)
    return AlertResponse.model_validate(alert)


@router.patch("/{alert_id}", response_model=AlertResponse)
async def update_alert(
    alert_id: uuid.UUID,
    payload: AlertUpdate,
    user: CurrentUser,
    db: DbSession,
) -> AlertResponse:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot edit alerts")
    service = AlertService(db)
    alert = await service.update_alert(alert_id, user.organization_id, payload)
    return AlertResponse.model_validate(alert)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    if not UserRole(user.role).can_edit_dashboards():
        raise PermissionDeniedError("You cannot delete alerts")

    service = AlertService(db)
    await service.delete_alert(alert_id, user.organization_id)

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Notifications -----------------------------------------------

notif_router = APIRouter(prefix="/notifications", tags=["notifications"])


@notif_router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    unread_only: bool = Query(False),
    limit: int = Query(50, le=200),
) -> list[NotificationResponse]:
    stmt = (
        select(Notification)
        .where(Notification.organization_id == user.organization_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))

    result = await db.execute(stmt)
    return [NotificationResponse.model_validate(n) for n in result.scalars()]


@notif_router.get("/unread-count")
async def unread_count(user: CurrentUser, db: DbSession) -> dict[str, int]:
    count = await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.organization_id == user.organization_id,
            Notification.is_read.is_(False),
        )
    )
    return {"unread": int(count or 0)}


@notif_router.post("/{notif_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notif_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    await db.execute(
        update(Notification)
        .where(
            Notification.id == notif_id,
            Notification.organization_id == user.organization_id,
        )
        .values(is_read=True)
    )

    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@notif_router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    user: CurrentUser,
    db: DbSession,
) -> Response:
    await db.execute(
        update(Notification)
        .where(
            Notification.organization_id == user.organization_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True)
    )

    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
