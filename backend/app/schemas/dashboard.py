# Schemas for metric queries, widgets, and dashboards- same schema is used for widget queries AND alert evaluations.

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import AggregationType, ChartType, TimeGranularity
from app.schemas.common import ORMModel

# Query primitives

FilterOperator = Literal["eq", "neq", "in", "not_in", "gt", "gte", "lt", "lte", "contains"]

# A single filter clause applied to events
class FilterCondition(BaseModel):
    field: str = Field(
        min_length=1,
        max_length=128,
        description="event_name | source | user_id | session_id | properties.<path>",
    )
    operator: FilterOperator
    value: Any

    @field_validator("field")
    @classmethod
    def validate_field(cls, v: str) -> str:
        import re

        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", v):
            raise ValueError("Invalid field name")
        return v

# Absolute or relative time range
class TimeRange(BaseModel):
    start: datetime | None = None
    end: datetime | None = None
    relative: str | None = Field(default=None, pattern=r"^\d+[mhdw]$")

    @model_validator(mode="after")
    def validate_one_of(self) -> "TimeRange":
        if self.relative is None and self.start is None:
            raise ValueError("Either `relative` or `start` is required")
        if self.relative is None and self.end is None:
            raise ValueError("`end` is required when using absolute range")
        if self.start and self.end and self.start >= self.end:
            raise ValueError("`start` must be before `end`")
        return self

# Declarative metric query
class MetricQuery(BaseModel):
    model_config = ConfigDict(extra='ignore')
    event_name: str | None = Field(default=None, max_length=128)
    source: str | None = Field(default=None, max_length=64)

    aggregation: AggregationType
    value_field: str | None = Field(
        default=None,
        description="Required for sum/avg/min/max. Use 'value' or 'properties.<field>'",
    )

    filters: list[FilterCondition] = Field(default_factory=list, max_length=20)
    group_by: list[str] = Field(default_factory=list, max_length=5)
    granularity: TimeGranularity | None = None
    time_range: TimeRange

    limit: int = Field(default=1000, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_aggregation_requires_value(self) -> "MetricQuery":
        needs_value = {
            AggregationType.SUM,
            AggregationType.AVG,
            AggregationType.MIN,
            AggregationType.MAX,
        }
        if self.aggregation in needs_value and not self.value_field:
            raise ValueError(f"Aggregation '{self.aggregation}' requires `value_field`")
        return self

    @field_validator("group_by")
    @classmethod
    def validate_group_by_fields(cls, v: list[str]) -> list[str]:
        import re

        for f in v:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_.]*$", f):
                raise ValueError(f"Invalid group_by field: {f}")
        return v


# Query results
# TimeSeries
class TimeSeriesPoint(BaseModel):
    timestamp: datetime
    value: float
    group: str | None = None

# Result of executing a MetricQuery
class MetricQueryResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    aggregation: AggregationType
    granularity: TimeGranularity | None
    points: list[TimeSeriesPoint]
    total: float  
    metadata: dict[str, Any] = Field(default_factory=dict)


# Widget 
# Widget Layout
class WidgetLayout(BaseModel):
    x: int = Field(default=0, ge=0, le=12)
    y: int = Field(default=0, ge=0)
    w: int = Field(default=6, ge=1, le=12)
    h: int = Field(default=4, ge=1, le=20)

# Create Widget
class WidgetCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    chart_type: ChartType
    query_config: MetricQuery
    layout: WidgetLayout = Field(default_factory=WidgetLayout)
    position: int = 0

# Update Widget
class WidgetUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    chart_type: ChartType | None = None
    query_config: MetricQuery | None = None
    layout: WidgetLayout | None = None
    position: int | None = None

# Widget Response
class WidgetResponse(ORMModel):
    id: UUID
    dashboard_id: UUID
    title: str
    chart_type: ChartType
    query_config: dict[str, Any]
    layout: dict[str, Any]
    position: int
    created_at: datetime
    updated_at: datetime


# Dashboard 
# Create Dashboard
class DashboardCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    refresh_interval: int = Field(default=0, ge=0, le=3600)
    is_public: bool = False

# Update Dashboard
class DashboardUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    refresh_interval: int | None = Field(default=None, ge=0, le=3600)
    is_public: bool | None = None

# Dashboard Summary Response- List view
class DashboardSummaryResponse(ORMModel):
    id: UUID
    name: str
    description: str | None
    is_public: bool
    refresh_interval: int
    created_at: datetime
    updated_at: datetime

# Dashboard Response
class DashboardResponse(DashboardSummaryResponse):
    widgets: list[WidgetResponse]
    share_token: str | None = None
