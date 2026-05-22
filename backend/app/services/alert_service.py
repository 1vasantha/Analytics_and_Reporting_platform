"""Alert service.

Two responsibilities:
  1. CRUD for alert definitions.
  2. Evaluation: invoked on a schedule, evaluates the alert's MetricQuery
     against its threshold, and fires notifications if breached (respecting
     cooldown).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models.alert import Alert, Notification
from app.models.enums import AlertOperator, AlertStatus
from app.schemas.alert import AlertCreate, AlertUpdate
from app.schemas.dashboard import MetricQuery
from app.services.metric_service import MetricService

log = get_logger(__name__)


_OPERATOR_FN = {
    AlertOperator.GT: lambda a, b: a > b,
    AlertOperator.GTE: lambda a, b: a >= b,
    AlertOperator.LT: lambda a, b: a < b,
    AlertOperator.LTE: lambda a, b: a <= b,
    AlertOperator.EQ: lambda a, b: a == b,
    AlertOperator.NEQ: lambda a, b: a != b,
}


class AlertService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ---------- CRUD -----------------------------------------------------

    async def list_alerts(self, organization_id: uuid.UUID) -> list[Alert]:
        result = await self.db.execute(
            select(Alert)
            .where(Alert.organization_id == organization_id)
            .order_by(Alert.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_alert(
        self, alert_id: uuid.UUID, organization_id: uuid.UUID
    ) -> Alert:
        alert = await self.db.scalar(
            select(Alert).where(
                Alert.id == alert_id, Alert.organization_id == organization_id
            )
        )
        if not alert:
            raise NotFoundError("Alert not found")
        return alert

    async def create_alert(
        self,
        organization_id: uuid.UUID,
        created_by_id: uuid.UUID,
        payload: AlertCreate,
    ) -> Alert:
        alert = Alert(
            organization_id=organization_id,
            created_by_id=created_by_id,
            name=payload.name,
            description=payload.description,
            query_config=payload.query_config.model_dump(mode="json"),
            operator=payload.operator,
            threshold=payload.threshold,
            check_interval_seconds=payload.check_interval_seconds,
            cooldown_seconds=payload.cooldown_seconds,
            channels=[c.value for c in payload.channels],
            channel_config=payload.channel_config,
            is_enabled=payload.is_enabled,
            status=AlertStatus.OK,
        )
        self.db.add(alert)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def update_alert(
        self,
        alert_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: AlertUpdate,
    ) -> Alert:
        alert = await self.get_alert(alert_id, organization_id)
        data = payload.model_dump(exclude_unset=True, mode="json")
        for key, value in data.items():
            if key == "channels" and value is not None:
                value = [c if isinstance(c, str) else c.value for c in value]
            setattr(alert, key, value)
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def delete_alert(
        self, alert_id: uuid.UUID, organization_id: uuid.UUID
    ) -> None:
        alert = await self.get_alert(alert_id, organization_id)
        await self.db.delete(alert)
        await self.db.commit()

    # ---------- Evaluation -----------------------------------------------

    async def evaluate(self, alert: Alert) -> tuple[bool, float | None]:
        """Evaluate an alert. Returns (triggered, observed_value).

        Caller is responsible for emitting notifications when triggered.
        """
        query = MetricQuery.model_validate(alert.query_config)
        service = MetricService(self.db)
        result = await service.execute(alert.organization_id, query, use_cache=False)

        observed = result.total
        op_fn = _OPERATOR_FN[AlertOperator(alert.operator)]
        triggered = op_fn(observed, alert.threshold)

        now = datetime.now(UTC)
        alert.last_checked_at = now
        alert.last_value = observed

        # Respect cooldown
        in_cooldown = (
            alert.last_triggered_at
            and (now - alert.last_triggered_at.replace(tzinfo=UTC))
            < timedelta(seconds=alert.cooldown_seconds)
        )

        if triggered and not in_cooldown:
            alert.status = AlertStatus.TRIGGERED
            alert.last_triggered_at = now
            should_fire = True
        elif triggered and in_cooldown:
            alert.status = AlertStatus.TRIGGERED
            should_fire = False
        else:
            alert.status = AlertStatus.OK
            should_fire = False

        await self.db.commit()
        return should_fire, observed

    async def create_notification(
        self,
        alert: Alert,
        observed_value: float,
        *,
        user_id: uuid.UUID | None = None,
    ) -> Notification:
        """Create an in-app notification record."""
        notif = Notification(
            organization_id=alert.organization_id,
            alert_id=alert.id,
            user_id=user_id,
            title=f"Alert triggered: {alert.name}",
            message=(
                f"Metric value {observed_value:.2f} {alert.operator} "
                f"threshold {alert.threshold:.2f}"
            ),
            severity="warning",
            metadata_={
                "alert_id": str(alert.id),
                "observed": observed_value,
                "threshold": alert.threshold,
                "operator": alert.operator,
            },
        )
        self.db.add(notif)
        await self.db.commit()
        await self.db.refresh(notif)
        return notif
