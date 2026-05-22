# WebSocket connection management

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict

from fastapi import WebSocket

from app.core.logging import get_logger
from app.db.redis import get_redis

log = get_logger(__name__)

# In-memory registry of active WebSocket connections
class ConnectionManager:
    def __init__(self) -> None:
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

    # Send a message to all connections for an organization (this process only)
    async def broadcast_to_org(
        self, organization_id: uuid.UUID, message: dict
    ) -> None:
        async with self._lock:
            connections = list(self._connections.get(organization_id, set()))

        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception: 
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[organization_id].discard(ws)

    # Publish a message to all processes via Redis pub/sub
    @staticmethod
    async def publish_to_org(organization_id: uuid.UUID, message: dict) -> None:
        redis = get_redis()
        await redis.publish(
            f"org:{organization_id}:ws",
            json.dumps(message, default=str),
        )

    # Subscribe to all org WebSocket channels and forward to local connections.
    async def start_redis_listener(self) -> None:
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

    # Stop redis listener
    async def stop_redis_listener(self) -> None:
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
            self._listener_task = None

manager = ConnectionManager()
