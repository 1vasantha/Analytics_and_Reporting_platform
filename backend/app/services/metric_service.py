"""Metric query engine.

Translates a declarative `MetricQuery` (Pydantic model) into a parameterized
SQLAlchemy Core query that executes safely against the `events` table.

Key design choices:
  * NO string interpolation of user input — every value is bound as a parameter.
  * The set of column/property fields is validated against a whitelist by the
    Pydantic schema layer (alphanumeric + dot only).
  * Time bucketing uses `date_trunc()` so PostgreSQL can use the index.
  * Result caching keyed on (org_id, hash(query_json)).
  * The engine is stateless — only takes an AsyncSession.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import (
    Column,
    Float,
    and_,
    cast,
    func,
    literal_column,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.core.exceptions import ValidationError
from app.core.logging import get_logger
from app.db.redis import cache_get, cache_set
from app.models.enums import AggregationType, TimeGranularity
from app.models.event import Event
from app.schemas.dashboard import (
    FilterCondition,
    MetricQuery,
    MetricQueryResult,
    TimeRange,
    TimeSeriesPoint,
)

log = get_logger(__name__)

# Whitelist of top-level event columns that can be filtered/grouped on.
# Anything else must go through the `properties` JSONB field.
_TOP_LEVEL_COLUMNS: dict[str, Column] = {
    "event_name": Event.event_name,
    "source": Event.source,
    "user_id": Event.user_id,
    "session_id": Event.session_id,
    "value": Event.value,
}

# Map TimeGranularity to PostgreSQL date_trunc argument
_GRANULARITY_PG: dict[TimeGranularity, str] = {
    TimeGranularity.MINUTE: "minute",
    TimeGranularity.HOUR: "hour",
    TimeGranularity.DAY: "day",
    TimeGranularity.WEEK: "week",
    TimeGranularity.MONTH: "month",
}

_RELATIVE_RE = re.compile(r"^(\d+)([mhdw])$")
_RELATIVE_TO_DELTA: dict[str, callable] = {
    "m": lambda n: timedelta(minutes=n),
    "h": lambda n: timedelta(hours=n),
    "d": lambda n: timedelta(days=n),
    "w": lambda n: timedelta(weeks=n),
}


def _resolve_time_range(tr: TimeRange) -> tuple[datetime, datetime]:
    """Resolve a TimeRange into concrete UTC (start, end) datetimes."""
    end = datetime.now(UTC)
    if tr.relative:
        match = _RELATIVE_RE.match(tr.relative)
        if not match:
            raise ValidationError(f"Invalid relative time range: {tr.relative}")
        n, unit = int(match.group(1)), match.group(2)
        delta = _RELATIVE_TO_DELTA[unit](n)
        return end - delta, end

    assert tr.start is not None and tr.end is not None  # validated by Pydantic
    return tr.start, tr.end


def _resolve_field(field: str) -> ColumnElement[Any]:
    """Resolve a field name to a SQLAlchemy column expression.

    Top-level columns return the mapped column directly.
    Property paths (e.g. "properties.country") become `events.properties->>'country'`.
    """
    if field in _TOP_LEVEL_COLUMNS:
        return _TOP_LEVEL_COLUMNS[field]

    if field.startswith("properties."):
        # Strip the prefix, allow nested via -> for intermediate, ->> for final text
        path = field.removeprefix("properties.").split(".")
        expr: Any = Event.properties
        # Walk all but the last with ->
        for segment in path[:-1]:
            expr = expr[segment]
        # Final segment with ->> for text extraction
        return expr[path[-1]].astext

    raise ValidationError(f"Unknown field: {field}")


def _apply_filter(stmt: Any, cond: FilterCondition) -> Any:
    """Apply a single FilterCondition to a select statement."""
    col = _resolve_field(cond.field)

    if cond.operator == "eq":
        return stmt.where(col == cond.value)
    if cond.operator == "neq":
        return stmt.where(col != cond.value)
    if cond.operator == "in":
        if not isinstance(cond.value, list):
            raise ValidationError("Operator 'in' requires a list value")
        return stmt.where(col.in_(cond.value))
    if cond.operator == "not_in":
        if not isinstance(cond.value, list):
            raise ValidationError("Operator 'not_in' requires a list value")
        return stmt.where(col.notin_(cond.value))
    if cond.operator == "gt":
        return stmt.where(col > cond.value)
    if cond.operator == "gte":
        return stmt.where(col >= cond.value)
    if cond.operator == "lt":
        return stmt.where(col < cond.value)
    if cond.operator == "lte":
        return stmt.where(col <= cond.value)
    if cond.operator == "contains":
        return stmt.where(col.ilike(f"%{cond.value}%"))

    raise ValidationError(f"Unsupported operator: {cond.operator}")


def _aggregation_expr(query: MetricQuery) -> ColumnElement[float]:
    """Build the aggregation SQL expression."""
    agg = query.aggregation
    if agg == AggregationType.COUNT:
        return cast(func.count(Event.id), Float).label("value")

    if agg == AggregationType.DISTINCT_COUNT:
        col = _resolve_field(query.value_field or "user_id")
        return cast(func.count(func.distinct(col)), Float).label("value")

    # SUM/AVG/MIN/MAX need a numeric column. value_field is required (validated).
    assert query.value_field is not None
    value_col = _resolve_field(query.value_field)
    # Property values come back as text from ->>; cast to float defensively
    if query.value_field.startswith("properties."):
        value_col = cast(value_col, Float)

    func_map = {
        AggregationType.SUM: func.sum,
        AggregationType.AVG: func.avg,
        AggregationType.MIN: func.min,
        AggregationType.MAX: func.max,
    }
    return cast(func_map[agg](value_col), Float).label("value")


def _cache_key(org_id: uuid.UUID, query: MetricQuery) -> str:
    """Build a deterministic cache key from org + query."""
    payload = json.dumps(query.model_dump(mode="json"), sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return f"metric:{org_id}:{digest}"


def _cache_ttl(query: MetricQuery) -> int:
    """Pick a cache TTL appropriate for the query's granularity."""
    if query.granularity == TimeGranularity.MINUTE:
        return 15
    if query.granularity == TimeGranularity.HOUR:
        return 60
    if query.granularity == TimeGranularity.DAY:
        return 300
    return 60


class MetricService:
    """Stateless service for executing metric queries."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def execute(
        self,
        organization_id: uuid.UUID,
        query: MetricQuery,
        *,
        use_cache: bool = True,
    ) -> MetricQueryResult:
        """Execute a MetricQuery and return the result.

        Cached in Redis with a granularity-aware TTL.
        """
        cache_key = _cache_key(organization_id, query) if use_cache else None
        if cache_key:
            cached = await cache_get(cache_key)
            if cached:
                log.debug("metric.cache_hit", cache_key=cache_key)
                return MetricQueryResult.model_validate(cached)

        start, end = _resolve_time_range(query.time_range)

        # Build base SELECT
        select_cols: list[Any] = [_aggregation_expr(query)]
        group_cols: list[Any] = []

        # Time bucketing
        time_col: ColumnElement[datetime] | None = None
        if query.granularity:
            time_col = func.date_trunc(
                _GRANULARITY_PG[query.granularity], Event.occurred_at
            ).label("ts")
            select_cols.insert(0, time_col)
            group_cols.append(time_col)

        # Additional group_by dimensions
        dimension_cols: list[ColumnElement[Any]] = []
        for field in query.group_by:
            col = _resolve_field(field).label(f"dim_{len(dimension_cols)}")
            dimension_cols.append(col)
            select_cols.append(col)
            group_cols.append(col)

        # Build statement
        stmt = select(*select_cols).where(
            and_(
                Event.organization_id == organization_id,
                Event.occurred_at >= start,
                Event.occurred_at < end,
            )
        )

        # Top-level fast-path filters
        if query.event_name:
            stmt = stmt.where(Event.event_name == query.event_name)
        if query.source:
            stmt = stmt.where(Event.source == query.source)

        # User filters
        for cond in query.filters:
            stmt = _apply_filter(stmt, cond)

        # Group / order / limit
        if group_cols:
            stmt = stmt.group_by(*group_cols)

        # Sort: time ascending for time series, value descending for ranked
        if time_col is not None:
            stmt = stmt.order_by(time_col.asc())
        else:
            stmt = stmt.order_by(literal_column("value").desc().nulls_last())

        stmt = stmt.limit(query.limit)

        log.debug(
            "metric.execute",
            org_id=str(organization_id),
            aggregation=query.aggregation,
            granularity=query.granularity,
            group_by=query.group_by,
        )

        rows = (await self.db.execute(stmt)).all()
        points = self._rows_to_points(rows, has_time=time_col is not None, num_dims=len(dimension_cols))

        total = sum(p.value for p in points) if query.aggregation in (
            AggregationType.COUNT,
            AggregationType.SUM,
            AggregationType.DISTINCT_COUNT,
        ) else (points[-1].value if points else 0.0)

        result = MetricQueryResult(
            aggregation=query.aggregation,
            granularity=query.granularity,
            points=points,
            total=total,
            metadata={
                "start": start.isoformat(),
                "end": end.isoformat(),
                "row_count": len(points),
            },
        )

        if cache_key:
            await cache_set(
                cache_key,
                result.model_dump(mode="json"),
                ttl_seconds=_cache_ttl(query),
            )

        return result

    @staticmethod
    def _rows_to_points(
        rows: list[Any], *, has_time: bool, num_dims: int
    ) -> list[TimeSeriesPoint]:
        """Convert raw query rows into TimeSeriesPoint records."""
        points: list[TimeSeriesPoint] = []
        for row in rows:
            data = row._mapping  # SQLAlchemy Row -> dict-like
            ts = data["ts"] if has_time else datetime.now(UTC)
            value = data["value"] or 0.0

            group: str | None = None
            if num_dims > 0:
                group_parts = [str(data[f"dim_{i}"]) for i in range(num_dims)]
                group = " · ".join(group_parts)

            points.append(TimeSeriesPoint(timestamp=ts, value=float(value), group=group))
        return points
