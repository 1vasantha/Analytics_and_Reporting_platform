"""Data ingestion endpoints.

Two auth modes are supported:
  * Bearer JWT (interactive — for in-app testing)
  * X-API-Key header (programmatic — preferred for production ingestion)

Endpoints:
  POST /ingest/events           single event
  POST /ingest/events/batch     batch events (up to 1000)
  POST /ingest/csv              CSV upload (async via Celery)
  GET  /ingest/jobs             list ingestion jobs
  GET  /ingest/jobs/{id}        get one job
  CRUD /ingest/api-keys
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status,Response
from sqlalchemy import select

from app.api.deps import ApiKeyAuth, CurrentUser, DbSession, get_api_key
from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.api_key import ApiKey
from app.models.enums import IngestionJobStatus
from app.models.event import IngestionJob
from app.schemas.event import (
    ApiKeyCreate,
    ApiKeyCreatedResponse,
    ApiKeyResponse,
    EventBatchCreate,
    EventCreate,
    IngestionJobResponse,
    IngestionResponse,
)
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingest", tags=["ingestion"])


# ---------- Event ingest (API key) --------------------------------------


@router.post(
    "/events",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a single event",
)
async def ingest_event(
    payload: EventCreate,
    api_key: ApiKeyAuth,
    db: DbSession,
    background: BackgroundTasks,
) -> IngestionResponse:
    service = IngestionService(db)
    await service.ingest_single(api_key.organization_id, payload)
    background.add_task(service.update_api_key_usage, api_key.id)
    return IngestionResponse(accepted=1, queued=False)


@router.post(
    "/events/batch",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of events (up to 1000)",
)
async def ingest_batch(
    payload: EventBatchCreate,
    api_key: ApiKeyAuth,
    db: DbSession,
    background: BackgroundTasks,
) -> IngestionResponse:
    service = IngestionService(db)
    accepted = await service.ingest_batch(api_key.organization_id, payload.events)
    background.add_task(service.update_api_key_usage, api_key.id)
    return IngestionResponse(accepted=accepted, queued=False)


# ---------- CSV upload (JWT-authenticated, async) -----------------------


@router.post(
    "/csv",
    response_model=IngestionJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a CSV of events for asynchronous processing",
)
async def upload_csv(
    user: CurrentUser,
    db: DbSession,
    file: Annotated[UploadFile, File(...)],
) -> IngestionJobResponse:
    if not file.filename or not file.filename.endswith(".csv"):
        raise BadRequestError("File must be a CSV")

    # Read file content (limited size)
    max_bytes = settings.MAX_CSV_SIZE_MB * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise BadRequestError(f"CSV exceeds {settings.MAX_CSV_SIZE_MB}MB limit")

    job = IngestionJob(
        organization_id=user.organization_id,
        created_by_id=user.id,
        filename=file.filename,
        status=IngestionJobStatus.PENDING.value,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Persist file for the worker to pick up. In production this would be S3.
    import os

    upload_dir = "/tmp/csv_uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, f"{job.id}.csv")
    with open(file_path, "wb") as f:
        f.write(content)

    # Enqueue the Celery task
    from app.workers.tasks import process_csv_ingestion

    process_csv_ingestion.delay(str(job.id), file_path)

    return IngestionJobResponse.model_validate(job)


@router.get("/jobs", response_model=list[IngestionJobResponse])
async def list_jobs(user: CurrentUser, db: DbSession) -> list[IngestionJobResponse]:
    result = await db.execute(
        select(IngestionJob)
        .where(IngestionJob.organization_id == user.organization_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(50)
    )
    return [IngestionJobResponse.model_validate(j) for j in result.scalars()]


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job(
    job_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> IngestionJobResponse:
    job = await db.scalar(
        select(IngestionJob).where(
            IngestionJob.id == job_id,
            IngestionJob.organization_id == user.organization_id,
        )
    )
    if not job:
        raise NotFoundError("Ingestion job not found")
    return IngestionJobResponse.model_validate(job)


# ---------- API key management ------------------------------------------


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(user: CurrentUser, db: DbSession) -> list[ApiKeyResponse]:
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == user.organization_id)
        .order_by(ApiKey.created_at.desc())
    )
    return [ApiKeyResponse.model_validate(k) for k in result.scalars()]


@router.post(
    "/api-keys",
    response_model=ApiKeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_api_key(
    payload: ApiKeyCreate, user: CurrentUser, db: DbSession
) -> ApiKeyCreatedResponse:
    full_key, prefix, hashed = ApiKey.generate()
    key = ApiKey(
        organization_id=user.organization_id,
        created_by_id=user.id,
        name=payload.name,
        prefix=prefix,
        hashed_key=hashed,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return ApiKeyCreatedResponse(id=key.id, name=key.name, key=full_key, prefix=prefix)


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    key = await db.scalar(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.organization_id == user.organization_id,
        )
    )

    if not key:
        raise NotFoundError("API key not found")

    key.revoked = True
    await db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
