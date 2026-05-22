# Event ingestion service- Single event,  Batch , CSV upload, invalidate cached metric results, Publish a "new_events" 

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.redis import cache_delete_pattern, get_redis
from app.models.api_key import ApiKey
from app.models.event import Event
from app.schemas.event import EventCreate

log = get_logger(__name__)

# Service for persisting events into the time-series store
class IngestionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # Persist a single event and return the saved row
    async def ingest_single(self, organization_id: uuid.UUID, event: EventCreate) -> Event:
        row = self._build_event_row(organization_id, event)
        obj = Event(**row)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

        await self._post_ingest(organization_id, count=1)
        return obj

    # Bulk insert events. Returns the number accepted
    async def ingest_batch(
        self, organization_id: uuid.UUID, events: list[EventCreate]
    ) -> int:
        if not events:
            return 0

        rows = [self._build_event_row(organization_id, e) for e in events]

        stmt = pg_insert(Event).values(rows)
        await self.db.execute(stmt)
        await self.db.commit()

        log.info(
            "ingestion.batch org_id=%s count=%s",
            organization_id,
            len(rows),
        )
        await self._post_ingest(organization_id, count=len(rows))
        return len(rows)

    # Update the last_used_at timestamp on an API key (fire-and-forget)
    async def update_api_key_usage(self, api_key_id: uuid.UUID) -> None:
        await self.db.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key_id)
            .values(last_used_at=datetime.now())
        )
        await self.db.commit()

    # Convert an EventCreate into a dict ready for bulk insert
    @staticmethod
    def _build_event_row(
        organization_id: uuid.UUID, event: EventCreate
    ) -> dict[str, Any]:
        now = datetime.now()
        return {
            "id": uuid.uuid4(),
            "organization_id": organization_id,
            "event_name": event.event_name,
            "source": event.source,
            "user_id": event.user_id,
            "session_id": event.session_id,
            "value": event.value,
            "properties": event.properties,
            "occurred_at": event.occurred_at or now,
            "ingested_at": now,
        }

    # Side effects after a successful ingest
    async def _post_ingest(self, organization_id: uuid.UUID, *, count: int) -> None:
        try:
            deleted = await cache_delete_pattern(f"metric:{organization_id}:*")
            if deleted:
                log.debug("ingestion.cache_invalidated", count=deleted)

            redis = get_redis()
            await redis.publish(
                f"org:{organization_id}:events",
                json.dumps({"type": "new_events", "count": count}),
            )
        except Exception:
            log.exception("ingestion.post_ingest_failed")
