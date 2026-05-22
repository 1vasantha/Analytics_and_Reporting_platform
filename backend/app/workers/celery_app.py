# Celery application factory

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "analytics_platform",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    task_acks_late=True,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=200,
    broker_connection_retry_on_startup=True,
)

# Periodic tasks
celery_app.conf.beat_schedule = {
    "evaluate-alerts": {
        "task": "app.workers.tasks.evaluate_all_alerts",
        "schedule": 60.0,
    },
    "send-scheduled-reports": {
        "task": "app.workers.tasks.run_scheduled_reports",
        "schedule": 60.0,
    },
    "cleanup-old-notifications": {
        "task": "app.workers.tasks.cleanup_old_notifications",
        "schedule": crontab(hour=3, minute=0), 
    },
}
