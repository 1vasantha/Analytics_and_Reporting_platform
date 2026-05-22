"""WebSocket endpoint for real-time dashboard updates.
Connection URL: /ws?token=<access_jwt>
Client receives JSON messages:
    {"type": "events_ingested", "count": 12}
    {"type": "notification", "id": "...", "title": "...", "message": "..."}
    {"type": "alert_triggered", "alert_id": "...", "value": 1234}
    {"type": "ping"} — sent every 30s; client should reply with pong
"""

from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError

from app.core.logging import get_logger
from app.core.security import decode_token
from app.websockets.manager import manager

router = APIRouter()
log = get_logger(__name__)

# Authenticated WebSocket endpoint
@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket, token: str = Query(...)
) -> None:
    try:
        payload = decode_token(token)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    if payload.type != "access" or not payload.org:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        organization_id = uuid.UUID(payload.org)
    except ValueError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(websocket, organization_id)
    await websocket.send_json({"type": "connected", "org": str(organization_id)})

    try:
        async def keepalive() -> None:
            while True:
                await asyncio.sleep(30)
                await websocket.send_json({"type": "ping"})

        async def reader() -> None:
            while True:
                await websocket.receive_text()

        keepalive_task = asyncio.create_task(keepalive())
        reader_task = asyncio.create_task(reader())

        done, pending = await asyncio.wait(
            {keepalive_task, reader_task},
            return_when=asyncio.FIRST_EXCEPTION,
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("ws.error", org_id=str(organization_id))
    finally:
        await manager.disconnect(websocket, organization_id)
