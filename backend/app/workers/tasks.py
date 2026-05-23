# Celery task definitions.
from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pandas as pd
from celery.utils.log import get_task_logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import (
    async_sessionmaker)
# from app.db.session import AsyncSessionLocal
from app.models.alert import Alert, Notification, ScheduledReport
from app.models.enums import IngestionJobStatus, NotificationChannel, ReportFrequency
from app.models.event import IngestionJob
from app.models.organization import Organization
from app.schemas.dashboard import MetricQuery
from app.schemas.event import EventCreate
from app.services.alert_service import AlertService
from app.services.email_service import get_email_service
from app.services.ingestion_service import IngestionService
from app.services.metric_service import MetricService
from app.workers.celery_app import celery_app

log = get_task_logger(__name__)

# Run an async coroutine from within a sync Celery task
def _run(coro: Any) -> Any:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(None)

def _make_session() -> async_sessionmaker:
    """Always create a fresh engine for Celery workers to avoid loop conflicts."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from app.core.config import settings

    engine = create_async_engine(
        str(settings.DATABASE_URL),
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    return async_sessionmaker(engine, expire_on_commit=False)

# CSV ingestion- Process an uploaded CSV file in chunks
@celery_app.task(name="app.workers.tasks.process_csv_ingestion", bind=True, max_retries=2)
def process_csv_ingestion(self, job_id: str, file_path: str) -> dict[str, int]:
    return _run(_process_csv(job_id, file_path))

# Process csv file
async def _process_csv(job_id_str: str, file_path: str) -> dict[str, int]:
    job_id = uuid.UUID(job_id_str)
    async with _make_session()() as db:
        job = await db.get(IngestionJob, job_id)
        if not job:
            log.error("csv.job_not_found", job_id=str(job_id))
            return {"processed": 0, "failed": 0}

        job.status = IngestionJobStatus.PROCESSING.value
        await db.commit()

        org_id = job.organization_id
        service = IngestionService(db)
        processed = 0
        failed = 0
        chunk_size = 500

        try:
            for chunk_df in pd.read_csv(file_path, chunksize=chunk_size):
                chunk_df = chunk_df.fillna("")
                events: list[EventCreate] = []

                for _, row in chunk_df.iterrows():
                    try:
                        row_dict = row.to_dict()
                        if not row_dict.get("event_name"):
                            failed += 1
                            continue

                        properties: dict[str, Any] = {}
                        reserved = {
                            "event_name",
                            "source",
                            "user_id",
                            "session_id",
                            "value",
                            "occurred_at",
                        }
                        for k, v in row_dict.items():
                            if k not in reserved and v != "":
                                properties[k] = v

                        value: float | None = None
                        if row_dict.get("value") not in (None, ""):
                            try:
                                value = float(row_dict["value"])
                            except (ValueError, TypeError):
                                pass

                        occurred_at: datetime | None = None
                        if row_dict.get("occurred_at"):
                            try:
                                occurred_at = pd.to_datetime(
                                    row_dict["occurred_at"], utc=True
                                ).to_pydatetime()
                            except Exception:
                                pass

                        events.append(
                            EventCreate(
                                event_name=str(row_dict["event_name"]),
                                source=str(row_dict.get("source") or "csv"),
                                user_id=str(row_dict["user_id"])
                                if row_dict.get("user_id")
                                else None,
                                session_id=str(row_dict["session_id"])
                                if row_dict.get("session_id")
                                else None,
                                value=value,
                                properties=properties,
                                occurred_at=occurred_at,
                            )
                        )
                    except Exception as exc: 
                        log.warning("csv.row_failed", error=str(exc))
                        failed += 1

                if events:
                    inserted = await service.ingest_batch(org_id, events)
                    processed += inserted

                job.processed_rows = processed
                job.failed_rows = failed
                await db.commit()

            job.status = IngestionJobStatus.COMPLETED.value
            job.total_rows = processed + failed
            job.completed_at = datetime.now(UTC)
            await db.commit()
            log.info(
                "csv.completed job_id=%s processed=%s failed=%s",
                job_id,
                processed,
                failed,
            )
        except Exception as exc: 
            log.exception("csv.failed", job_id=str(job_id))
            job.status = IngestionJobStatus.FAILED.value
            job.error_message = str(exc)[:1024]
            job.completed_at = datetime.now(UTC)
            await db.commit()
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

        return {"processed": processed, "failed": failed}

# Alert evaluation
# Evaluate every enabled alert. Called every minute by Beat
@celery_app.task(name="app.workers.tasks.evaluate_all_alerts")
def evaluate_all_alerts() -> dict[str, int]:
    return _run(_evaluate_all_alerts())

# Evaluate all alerts
async def _evaluate_all_alerts() -> dict[str, int]:
    fired = 0
    checked = 0

    async with _make_session()() as db:
        alerts = (
            await db.execute(select(Alert).where(Alert.is_enabled.is_(True)))
        ).scalars().all()

        service = AlertService(db)
        for alert in alerts:
            checked += 1
            try:
                if alert.last_checked_at:
                    since = (
                        datetime.now(UTC) - alert.last_checked_at.replace(tzinfo=UTC)
                    ).total_seconds()
                    if since < alert.check_interval_seconds - 5:
                        continue

                should_fire, observed = await service.evaluate(alert)
                if should_fire and observed is not None:
                    fired += 1
                    await _emit_alert_notifications(db, alert, observed)
            except Exception:
                log.exception("alert.eval_failed", alert_id=str(alert.id))

    log.info(
        "alerts.evaluated checked=%s fired=%s",
        checked,
        fired,
    )
    return {"checked": checked, "fired": fired}

# Emit notifications across all configured channels
async def _emit_alert_notifications(
    db: Any, alert: Alert, observed_value: float
) -> None:
    service = AlertService(db)
    notif = await service.create_notification(alert, observed_value)

    from app.websockets.manager import manager as ws_manager

    await ws_manager.publish_to_org(
        alert.organization_id,
        {
            "type": "alert_triggered",
            "notification_id": str(notif.id),
            "alert_id": str(alert.id),
            "title": notif.title,
            "message": notif.message,
            "observed": observed_value,
            "threshold": alert.threshold,
        },
    )

    # Email
    if NotificationChannel.EMAIL.value in alert.channels:
        recipients = alert.channel_config.get("email_recipients", [])
        if recipients:
            org = await db.get(Organization, alert.organization_id)
            email_svc = get_email_service()
            html = await email_svc.render_template(
                "alert_triggered.html",
                alert=alert,
                observed_value=f"{observed_value:.2f}",
                triggered_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
                organization_name=org.name if org else "Your organization",
                frontend_url=_frontend_url(),
            )
            await email_svc.send(
                to=recipients,
                subject=f"[Alert] {alert.name}",
                html=html,
            )

    # Webhook
    if NotificationChannel.WEBHOOK.value in alert.channels:
        url = alert.channel_config.get("webhook_url")
        if url:
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    await client.post(
                        url,
                        json={
                            "alert_id": str(alert.id),
                            "alert_name": alert.name,
                            "observed_value": observed_value,
                            "threshold": alert.threshold,
                            "operator": alert.operator,
                            "triggered_at": datetime.now(UTC).isoformat(),
                        },
                    )
            except Exception:
                log.warning("alert.webhook_failed", alert_id=str(alert.id))

def _frontend_url() -> str:
    from app.core.config import settings

    return settings.FRONTEND_URL

# Scheduled reports

_FREQUENCY_DELTA = {
    ReportFrequency.DAILY: timedelta(days=1),
    ReportFrequency.WEEKLY: timedelta(weeks=1),
    ReportFrequency.MONTHLY: timedelta(days=30),
}

_FREQUENCY_LABEL = {
    ReportFrequency.DAILY: "Daily",
    ReportFrequency.WEEKLY: "Weekly",
    ReportFrequency.MONTHLY: "Monthly",
}

@celery_app.task(name="app.workers.tasks.run_scheduled_reports")
def run_scheduled_reports() -> dict[str, int]:
    return _run(_run_scheduled_reports())

async def _run_scheduled_reports() -> dict[str, int]:
    now = datetime.now(UTC)
    sent = 0

    async with _make_session()() as db:
        from sqlalchemy.orm import selectinload
        from app.models.dashboard import Dashboard

        stmt = (
            select(ScheduledReport)
            .where(
                ScheduledReport.is_enabled.is_(True),
                ScheduledReport.next_run_at.is_not(None),
                ScheduledReport.next_run_at <= now,
            )
        )
        reports = (await db.execute(stmt)).scalars().all()

        email_svc = get_email_service()
        metric_svc = MetricService(db)

        for report in reports:
            try:
                dashboard = await db.scalar(
                    select(Dashboard)
                    .options(selectinload(Dashboard.widgets))
                    .where(Dashboard.id == report.dashboard_id)
                )
                if not dashboard:
                    continue

                widget_data = []
                for widget in dashboard.widgets:
                    query = MetricQuery.model_validate(widget.query_config)
                    result = await metric_svc.execute(
                        dashboard.organization_id, query, use_cache=False
                    )
                    widget_data.append(
                        {
                            "title": widget.title,
                            "total": result.total,
                            "aggregation": result.aggregation,
                            "row_count": len(result.points),
                        }
                    )

                freq = ReportFrequency(report.frequency)
                html = await email_svc.render_template(
                    "dashboard_report.html",
                    dashboard=dashboard,
                    widgets=widget_data,
                    frequency_label=_FREQUENCY_LABEL[freq],
                    generated_at=now.strftime("%Y-%m-%d %H:%M UTC"),
                    frontend_url=_frontend_url(),
                )
                await email_svc.send(
                    to=list(report.recipients),
                    subject=f"[{_FREQUENCY_LABEL[freq]} Report] {dashboard.name}",
                    html=html,
                )

                report.last_sent_at = now
                report.next_run_at = now + _FREQUENCY_DELTA[freq]
                await db.commit()
                sent += 1
            except Exception: 
                log.exception("report.send_failed", report_id=str(report.id))

    log.info(
        "reports.sent count=%s",
        sent,
    )
    return {"sent": sent}


# Maintenance
# Delete read notifications older than 30 days
@celery_app.task(name="app.workers.tasks.cleanup_old_notifications")
def cleanup_old_notifications() -> dict[str, int]:
    return _run(_cleanup_old_notifications())

async def _cleanup_old_notifications() -> dict[str, int]:
    cutoff = datetime.now(UTC) - timedelta(days=30)
    async with _make_session()() as db:
        result = await db.execute(
            delete(Notification).where(
                Notification.is_read.is_(True),
                Notification.created_at < cutoff,
            )
        )
        await db.commit()
        deleted = result.rowcount or 0
    log.info(
        "notifications.cleaned deleted=%s",
        deleted,
    )
    return {"deleted": deleted}
