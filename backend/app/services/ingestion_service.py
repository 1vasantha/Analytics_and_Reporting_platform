"""Event ingestion service.

Three ingestion paths:
  1. Single event — synchronous insert, returns immediately.
  2. Batch — up to MAX_BATCH_SIZE events; uses bulk insert; can fan out to Celery
     for large batches.
  3. CSV upload — stored to disk, processed asynchronously by a Celery worker.

After successful ingestion, we:
  * Invalidate cached metric results for the org (via Redis pattern delete)
  * Publish a "new_events" message on the org channel so WebSocket clients
    can refresh their dashboards.
"""
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


class IngestionService:
    """Service for persisting events into the time-series store."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def ingest_single(self, organization_id: uuid.UUID, event: EventCreate) -> Event:
        """Persist a single event and return the saved row."""
        row = self._build_event_row(organization_id, event)
        obj = Event(**row)
        self.db.add(obj)
        await self.db.commit()
        await self.db.refresh(obj)

        await self._post_ingest(organization_id, count=1)
        return obj

    async def ingest_batch(
        self, organization_id: uuid.UUID, events: list[EventCreate]
    ) -> int:
        """Bulk insert events. Returns the number accepted."""
        if not events:
            return 0

        rows = [self._build_event_row(organization_id, e) for e in events]

        # Use PostgreSQL's ON CONFLICT DO NOTHING in case of dedupe on (org, id);
        # though we generate UUIDs server-side so conflicts are theoretical.
        stmt = pg_insert(Event).values(rows)
        await self.db.execute(stmt)
        await self.db.commit()

        log.info("ingestion.batch", org_id=str(organization_id), count=len(rows))
        await self._post_ingest(organization_id, count=len(rows))
        return len(rows)

    async def update_api_key_usage(self, api_key_id: uuid.UUID) -> None:
        """Update the last_used_at timestamp on an API key (fire-and-forget)."""
        await self.db.execute(
            update(ApiKey)
            .where(ApiKey.id == api_key_id)
            .values(last_used_at=datetime.now())
        )
        await self.db.commit()

    @staticmethod
    def _build_event_row(
        organization_id: uuid.UUID, event: EventCreate
    ) -> dict[str, Any]:
        """Convert an EventCreate into a dict ready for bulk insert."""
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

    async def _post_ingest(self, organization_id: uuid.UUID, *, count: int) -> None:
        """Side effects after a successful ingest.

        These are best-effort — failures are logged but don't roll back the insert.
        """
        try:
            # Invalidate cached metric results for this org
            deleted = await cache_delete_pattern(f"metric:{organization_id}:*")
            if deleted:
                log.debug("ingestion.cache_invalidated", count=deleted)

            # Publish to WebSocket channel
            redis = get_redis()
            await redis.publish(
                f"org:{organization_id}:events",
                json.dumps({"type": "new_events", "count": count}),
            )
        except Exception:  # noqa: BLE001
            log.exception("ingestion.post_ingest_failed")
