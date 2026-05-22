# Seed the database with demo data.

from __future__ import annotations

import asyncio
import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.alert import Alert
from app.models.dashboard import Dashboard, Widget
from app.models.enums import (
    AggregationType,
    AlertOperator,
    AlertStatus,
    ChartType,
    NotificationChannel,
    TimeGranularity,
    UserRole,
)
from app.models.event import Event
from app.models.organization import Organization
from app.models.user import User

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demopass123"

async def seed() -> None:
    async with AsyncSessionLocal() as db:
        existing = await db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing:
            print(f"Demo user already exists: {DEMO_EMAIL}")
            print(f"Organization: {existing.organization_id}")
            return

        # Org + user
        org = Organization(name="Analytics Global", slug="acme")
        user = User(
            email=DEMO_EMAIL,
            full_name="Demo User",
            hashed_password=hash_password(DEMO_PASSWORD),
            organization=org,
            role=UserRole.OWNER,
            is_active=True,
            is_verified=True,
        )
        db.add(org)
        db.add(user)
        await db.commit()
        await db.refresh(org)
        await db.refresh(user)
        print(f"Created org: {org.id} ({org.slug})")
        print(f"Created user: {user.email} / {DEMO_PASSWORD}")

        # Events
        events_to_create: list[Event] = []
        now = datetime.now(UTC)
        countries = ["US", "GB", "DE", "FR", "JP", "BR", "IN", "CA"]
        sources = ["web", "ios", "android"]

        for day_offset in range(7):
            day = now - timedelta(days=day_offset)
            for _ in range(700):
                hour_weights = [
                    0.5, 0.3, 0.2, 0.1, 0.1, 0.2, 0.5, 1.0,
                    1.5, 2.0, 2.5, 2.0, 1.8, 1.5, 1.5, 1.5,
                    1.8, 2.0, 2.2, 2.5, 2.2, 1.8, 1.2, 0.8,
                ]
                hour = random.choices(range(24), weights=hour_weights, k=1)[0]
                minute = random.randint(0, 59)
                ts = day.replace(hour=hour, minute=minute, second=random.randint(0, 59))

                roll = random.random()
                if roll < 0.40:
                    name = "pageview"
                    value = None
                elif roll < 0.55:
                    name = "click"
                    value = None
                elif roll < 0.70:
                    name = "signup"
                    value = None
                elif roll < 0.90:
                    name = "purchase"
                    value = round(random.lognormvariate(3.5, 0.8), 2)
                else:
                    name = "error"
                    value = None

                events_to_create.append(
                    Event(
                        id=uuid.uuid4(),
                        organization_id=org.id,
                        event_name=name,
                        source=random.choice(sources),
                        user_id=f"user_{random.randint(1, 200)}",
                        session_id=f"sess_{random.randint(1, 500)}",
                        value=value,
                        properties={
                            "country": random.choice(countries),
                            "browser": random.choice(["chrome", "safari", "firefox", "edge"]),
                            "plan": random.choice(["free", "pro", "enterprise"]),
                        },
                        occurred_at=ts,
                        ingested_at=ts,
                    )
                )

        db.add_all(events_to_create)
        await db.commit()
        print(f"Created {len(events_to_create)} events")

        # Dashboard 1: Overview
        overview = Dashboard(
            organization_id=org.id,
            created_by_id=user.id,
            name="Product Overview",
            description="Top-line metrics across the product",
            refresh_interval=30,
            is_public=False,
        )
        db.add(overview)
        await db.commit()
        await db.refresh(overview)

        # KPI: total signups (last 7d)
        db.add(
            Widget(
                dashboard_id=overview.id,
                title="Signups (7d)",
                chart_type=ChartType.KPI.value,
                query_config={
                    "event_name": "signup",
                    "aggregation": AggregationType.COUNT.value,
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                layout={"x": 0, "y": 0, "w": 3, "h": 2},
                position=0,
            )
        )

        # KPI: total revenue
        db.add(
            Widget(
                dashboard_id=overview.id,
                title="Revenue (7d)",
                chart_type=ChartType.KPI.value,
                query_config={
                    "event_name": "purchase",
                    "aggregation": AggregationType.SUM.value,
                    "value_field": "value",
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                layout={"x": 3, "y": 0, "w": 3, "h": 2},
                position=1,
            )
        )

        # Line: daily pageviews
        db.add(
            Widget(
                dashboard_id=overview.id,
                title="Daily Pageviews",
                chart_type=ChartType.LINE.value,
                query_config={
                    "event_name": "pageview",
                    "aggregation": AggregationType.COUNT.value,
                    "granularity": TimeGranularity.DAY.value,
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                layout={"x": 6, "y": 0, "w": 6, "h": 4},
                position=2,
            )
        )

        # Bar: events by source
        db.add(
            Widget(
                dashboard_id=overview.id,
                title="Events by Source",
                chart_type=ChartType.BAR.value,
                query_config={
                    "aggregation": AggregationType.COUNT.value,
                    "group_by": ["source"],
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "limit": 100,
                },
                layout={"x": 0, "y": 4, "w": 6, "h": 4},
                position=3,
            )
        )

        # Pie: events by country
        db.add(
            Widget(
                dashboard_id=overview.id,
                title="Top Countries",
                chart_type=ChartType.PIE.value,
                query_config={
                    "aggregation": AggregationType.COUNT.value,
                    "group_by": ["properties.country"],
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "limit": 8,
                },
                layout={"x": 6, "y": 4, "w": 6, "h": 4},
                position=4,
            )
        )
        print(f"Created dashboard: {overview.name}")

        # Dashboard 2: Revenue
        revenue = Dashboard(
            organization_id=org.id,
            created_by_id=user.id,
            name="Revenue Analytics",
            description="Purchases, conversion, and revenue trends",
            refresh_interval=60,
        )
        db.add(revenue)
        await db.commit()
        await db.refresh(revenue)

        db.add(
            Widget(
                dashboard_id=revenue.id,
                title="Hourly Revenue (24h)",
                chart_type=ChartType.AREA.value,
                query_config={
                    "event_name": "purchase",
                    "aggregation": AggregationType.SUM.value,
                    "value_field": "value",
                    "granularity": TimeGranularity.HOUR.value,
                    "time_range": {"relative": "24h"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                layout={"x": 0, "y": 0, "w": 12, "h": 4},
                position=0,
            )
        )

        db.add(
            Widget(
                dashboard_id=revenue.id,
                title="Avg Order Value (7d)",
                chart_type=ChartType.KPI.value,
                query_config={
                    "event_name": "purchase",
                    "aggregation": AggregationType.AVG.value,
                    "value_field": "value",
                    "time_range": {"relative": "7d"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                layout={"x": 0, "y": 4, "w": 4, "h": 2},
                position=1,
            )
        )
        await db.commit()
        print(f"Created dashboard: {revenue.name}")

        # Alerts
        db.add(
            Alert(
                organization_id=org.id,
                created_by_id=user.id,
                name="High signup volume",
                description="Fires when signups exceed 100 in the last hour",
                query_config={
                    "event_name": "signup",
                    "aggregation": AggregationType.COUNT.value,
                    "time_range": {"relative": "1h"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                operator=AlertOperator.GT.value,
                threshold=100,
                check_interval_seconds=60,
                cooldown_seconds=600,
                channels=[NotificationChannel.IN_APP.value, NotificationChannel.EMAIL.value],
                channel_config={"email_recipients": [DEMO_EMAIL]},
                status=AlertStatus.OK.value,
                is_enabled=True,
            )
        )
        db.add(
            Alert(
                organization_id=org.id,
                created_by_id=user.id,
                name="Error spike",
                description="Fires when error count exceeds 20 in last 15 min",
                query_config={
                    "event_name": "error",
                    "aggregation": AggregationType.COUNT.value,
                    "time_range": {"relative": "15m"},
                    "filters": [],
                    "group_by": [],
                    "limit": 1000,
                },
                operator=AlertOperator.GT.value,
                threshold=20,
                check_interval_seconds=60,
                cooldown_seconds=300,
                channels=[NotificationChannel.IN_APP.value],
                channel_config={},
                status=AlertStatus.OK.value,
                is_enabled=True,
            )
        )
        await db.commit()
        print("Created 2 alerts")

        print("\n✅ Seed complete!")
        print(f"   Login: {DEMO_EMAIL} / {DEMO_PASSWORD}")

if __name__ == "__main__":
    asyncio.run(seed())
