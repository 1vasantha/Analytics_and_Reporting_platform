# numerated types used across the domain.
from __future__ import annotations

from enum import StrEnum

# Possible user roles
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
        return True

# Chart types
class ChartType(StrEnum):
    LINE = "line"
    BAR = "bar"
    PIE = "pie"
    KPI = "kpi"
    AREA = "area"
    TABLE = "table"

# Aggregation Types
class AggregationType(StrEnum):
    COUNT = "count"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    DISTINCT_COUNT = "distinct_count"

# Time Granularity
class TimeGranularity(StrEnum):
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

# Alert Operators
class AlertOperator(StrEnum):
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    EQ = "eq"
    NEQ = "neq"

# AlertStatus
class AlertStatus(StrEnum):
    OK = "ok"
    TRIGGERED = "triggered"
    SILENCED = "silenced"

# Notification Channels
class NotificationChannel(StrEnum):
    EMAIL = "email"
    IN_APP = "in_app"
    WEBHOOK = "webhook"

# IngestionJob  Status
class IngestionJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Report Cadence
class ReportFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
