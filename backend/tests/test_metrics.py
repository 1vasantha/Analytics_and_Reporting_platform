"""Tests for the metric query engine."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import AggregationType, TimeGranularity, UserRole
from app.models.event import Event
from app.models.organization import Organization
from app.models.user import User
from app.schemas.dashboard import FilterCondition, MetricQuery, TimeRange
from app.services.metric_service import MetricService


@pytest.fixture
async def org_with_events(db):
    """Create an org and 24 hourly events with mixed properties."""
    org = Organization(name="Test Org", slug=f"test-{uuid.uuid4().hex[:6]}")
    user = User(
        email=f"u{uuid.uuid4().hex[:6]}@t.com",
        full_name="Test",
        hashed_password="$2b$12$x",
        organization=org,
        role=UserRole.OWNER,
        is_active=True,
    )
    db.add(org)
    db.add(user)
    await db.flush()

    now = datetime.now(UTC)
    events = []
    for i in range(24):
        events.append(
            Event(
                organization_id=org.id,
                event_name="signup" if i % 3 == 0 else "pageview",
                source="web" if i % 2 == 0 else "ios",
                value=10.0 if i % 3 == 0 else None,
                properties={"country": "US" if i % 2 == 0 else "GB"},
                occurred_at=now - timedelta(hours=23 - i),
                ingested_at=now,
            )
        )
    db.add_all(events)
    await db.flush()
    return org


@pytest.mark.asyncio
async def test_count_total(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            event_name="signup",
            aggregation=AggregationType.COUNT,
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    # 24 events, every 3rd is signup -> 8 signups
    assert result.total == 8


@pytest.mark.asyncio
async def test_sum_value(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            event_name="signup",
            aggregation=AggregationType.SUM,
            value_field="value",
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    # 8 signups * 10.0 = 80
    assert result.total == 80


@pytest.mark.asyncio
async def test_hourly_granularity(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            aggregation=AggregationType.COUNT,
            granularity=TimeGranularity.HOUR,
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    assert len(result.points) > 0
    assert result.total > 0


@pytest.mark.asyncio
async def test_group_by_source(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            aggregation=AggregationType.COUNT,
            group_by=["source"],
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    groups = {p.group for p in result.points}
    assert groups == {"web", "ios"}


@pytest.mark.asyncio
async def test_filter_eq(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            aggregation=AggregationType.COUNT,
            filters=[FilterCondition(field="source", operator="eq", value="web")],
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    assert result.total == 12  # half of 24


@pytest.mark.asyncio
async def test_filter_property(org_with_events, db):
    svc = MetricService(db)
    result = await svc.execute(
        org_with_events.id,
        MetricQuery(
            aggregation=AggregationType.COUNT,
            filters=[FilterCondition(field="properties.country", operator="eq", value="US")],
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    assert result.total == 12


@pytest.mark.asyncio
async def test_org_isolation(org_with_events, db):
    other_id = uuid.uuid4()
    svc = MetricService(db)
    result = await svc.execute(
        other_id,
        MetricQuery(
            aggregation=AggregationType.COUNT,
            time_range=TimeRange(relative="24h"),
        ),
        use_cache=False,
    )
    assert result.total == 0
