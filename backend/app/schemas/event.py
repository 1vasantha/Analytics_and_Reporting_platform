"""Event ingestion schemas.

The single-event endpoint accepts one EventCreate.
The batch endpoint accepts up to MAX_BATCH_SIZE events.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.schemas.common import ORMModel


class EventCreate(BaseModel):
    """A single event to ingest."""

    event_name: str = Field(min_length=1, max_length=128)
    source: str = Field(default="api", max_length=64)
    user_id: str | None = Field(default=None, max_length=128)
    session_id: str | None = Field(default=None, max_length=128)
    value: float | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None  # if absent, server time is used

    @field_validator("properties")
    @classmethod
    def validate_properties_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        # Hard cap on individual event size to prevent abuse
        import json

        if len(json.dumps(v, default=str)) > 16_384:
            raise ValueError("properties exceed 16KB limit")
        return v


class EventBatchCreate(BaseModel):
    events: list[EventCreate] = Field(min_length=1)

    @field_validator("events")
    @classmethod
    def validate_batch_size(cls, v: list[EventCreate]) -> list[EventCreate]:
        if len(v) > settings.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds maximum of {settings.MAX_BATCH_SIZE}")
        return v


class IngestionResponse(BaseModel):
    accepted: int
    queued: bool = True
    job_id: UUID | None = None


class EventResponse(ORMModel):
    id: UUID
    event_name: str
    source: str
    user_id: str | None
    session_id: str | None
    value: float | None
    properties: dict[str, Any]
    occurred_at: datetime
    ingested_at: datetime


class IngestionJobResponse(ORMModel):
    id: UUID
    filename: str
    status: str
    total_rows: int
    processed_rows: int
    failed_rows: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)


class ApiKeyResponse(ORMModel):
    id: UUID
    name: str
    prefix: str
    created_at: datetime
    last_used_at: datetime | None
    revoked: bool


class ApiKeyCreatedResponse(BaseModel):
    """Returned ONCE on creation — includes the full key."""

    id: UUID
    name: str
    key: str  # full key, only shown here
    prefix: str
