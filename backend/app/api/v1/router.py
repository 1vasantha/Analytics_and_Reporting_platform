"""API v1 router aggregator."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import alerts, auth, dashboards, ingestion, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(ingestion.router)
api_router.include_router(dashboards.router)
api_router.include_router(alerts.router)
api_router.include_router(alerts.notif_router)
api_router.include_router(reports.router)
