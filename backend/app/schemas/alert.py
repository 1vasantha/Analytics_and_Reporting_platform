"""Alert, notification, and scheduled-report schemas."""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import (
    AlertOperator,
    AlertStatus,
    NotificationChannel,
    ReportFrequency,
)
from app.schemas.common import ORMModel
from app.schemas.dashboard import MetricQuery


class AlertCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    query_config: MetricQuery
    operator: AlertOperator
    threshold: float
    check_interval_seconds: int = Field(default=60, ge=30, le=86_400)
    cooldown_seconds: int = Field(default=300, ge=0, le=86_400)
    channels: list[NotificationChannel] = Field(min_length=1)
    channel_config: dict[str, Any] = Field(default_factory=dict)
    is_enabled: bool = True

    @field_validator("channels")
    @classmethod
    def dedupe_channels(cls, v: list[NotificationChannel]) -> list[NotificationChannel]:
        # Preserve order but remove dupes
        return list(dict.fromkeys(v))


class AlertUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    query_config: MetricQuery | None = None
    operator: AlertOperator | None = None
    threshold: float | None = None
    check_interval_seconds: int | None = Field(default=None, ge=30, le=86_400)
    cooldown_seconds: int | None = Field(default=None, ge=0, le=86_400)
    channels: list[NotificationChannel] | None = Field(default=None, min_length=1)
    channel_config: dict[str, Any] | None = None
    is_enabled: bool | None = None


class AlertResponse(ORMModel):
    id: UUID
    name: str
    description: str | None
    query_config: dict[str, Any]
    operator: AlertOperator
    threshold: float
    check_interval_seconds: int
    cooldown_seconds: int
    channels: list[str]
    channel_config: dict[str, Any]
    status: AlertStatus
    is_enabled: bool
    last_checked_at: datetime | None
    last_triggered_at: datetime | None
    last_value: float | None
    created_at: datetime
    updated_at: datetime


class NotificationResponse(ORMModel):
    id: UUID
    alert_id: UUID | None
    title: str
    message: str
    severity: str
    is_read: bool
    metadata: dict[str, Any] = Field(alias="metadata_")
    created_at: datetime


class ScheduledReportCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    dashboard_id: UUID
    frequency: ReportFrequency
    recipients: list[EmailStr] = Field(min_length=1, max_length=50)
    is_enabled: bool = True


class ScheduledReportUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    frequency: ReportFrequency | None = None
    recipients: list[EmailStr] | None = Field(default=None, min_length=1, max_length=50)
    is_enabled: bool | None = None


class ScheduledReportResponse(ORMModel):
    id: UUID
    name: str
    dashboard_id: UUID
    frequency: ReportFrequency
    recipients: list[str]
    is_enabled: bool
    last_sent_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
