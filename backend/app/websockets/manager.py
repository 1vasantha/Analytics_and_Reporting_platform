"""WebSocket connection management.

Each connected client subscribes to one organization channel. Updates flow
in two directions:

  Backend -> Client:
    * `new_events` — published by ingestion service when events arrive
    * `notification` — published when alerts fire
    * `metric_update` — pushed when dashboard widgets should refresh

We use Redis pub/sub so messages emitted from any process (web server, Celery
worker, beat scheduler) are fanned out to all WebSocket-serving processes.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict

from fastapi import WebSocket

from app.core.logging import get_logger
from app.db.redis import get_redis

log = get_logger(__name__)


class ConnectionManager:
    """In-memory registry of active WebSocket connections.

    One instance per worker process. Coordination across processes is handled
    by Redis pub/sub (see `start_redis_listener`).
    """

    def __init__(self) -> None:
        # org_id -> set of WebSocket connections
        self._connections: dict[uuid.UUID, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self._listener_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket, organization_id: uuid.UUID) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[organization_id].add(websocket)
        log.info(
            "ws.connected",
            org_id=str(organization_id),
            total=len(self._connections[organization_id]),
        )

    async def disconnect(
        self, websocket: WebSocket, organization_id: uuid.UUID
    ) -> None:
        async with self._lock:
            self._connections[organization_id].discard(websocket)
            if not self._connections[organization_id]:
                del self._connections[organization_id]
        log.info("ws.disconnected", org_id=str(organization_id))

    async def broadcast_to_org(
        self, organization_id: uuid.UUID, message: dict
    ) -> None:
        """Send a message to all connections for an organization (this process only).

        Cross-process broadcast goes through `publish_to_org` -> Redis -> listener.
        """
        async with self._lock:
            connections = list(self._connections.get(organization_id, set()))

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[organization_id].discard(ws)

    @staticmethod
    async def publish_to_org(organization_id: uuid.UUID, message: dict) -> None:
        """Publish a message to all processes via Redis pub/sub."""
        redis = get_redis()
        await redis.publish(
            f"org:{organization_id}:ws",
            json.dumps(message, default=str),
        )

    async def start_redis_listener(self) -> None:
        """Subscribe to all org WebSocket channels and forward to local connections."""
        if self._listener_task and not self._listener_task.done():
            return

        async def listen() -> None:
            redis = get_redis()
            pubsub = redis.pubsub()
            await pubsub.psubscribe("org:*:ws", "org:*:events")
            log.info("ws.listener.started")

            async for message in pubsub.listen():
                if message["type"] not in ("pmessage", "message"):
                    continue
                channel = (
                    message["channel"]
                    if isinstance(message["channel"], str)
                    else message["channel"].decode()
                )
                # channel format: "org:<uuid>:ws" or "org:<uuid>:events"
                try:
                    _, org_str, kind = channel.split(":")
                    org_id = uuid.UUID(org_str)
                except (ValueError, TypeError):
                    continue

                try:
                    data = json.loads(message["data"])
                except (TypeError, json.JSONDecodeError):
                    continue

                if kind == "events":
                    data = {"type": "events_ingested", **data}
                await self.broadcast_to_org(org_id, data)

        self._listener_task = asyncio.create_task(listen())

    async def stop_redis_listener(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None


# Singleton
manager = ConnectionManager()
