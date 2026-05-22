"""Enumerated types used across the domain."""
from __future__ import annotations

from enum import StrEnum


class UserRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"

    def can_manage_org(self) -> bool:
        return self in (UserRole.OWNER, UserRole.ADMIN)

    def can_edit_dashboards(self) -> bool:
        return self in (UserRole.OWNER, UserRole.ADMIN, UserRole.ANALYST)

    def can_view(self) -> bool:
        return True  # All roles can view


class ChartType(StrEnum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    KPI = "kpi"
    AREA = "area"
    TABLE = "table"


class AggregationType(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    DISTINCT_COUNT = "distinct_count"


class TimeGranularity(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class AlertOperator(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"


class AlertStatus(StrEnum):
    OK = "ok"
    TRIGGERED = "triggered"
    SILENCED = "silenced"


class NotificationChannel(StrEnum):
    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class IngestionJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReportFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
