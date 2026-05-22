# Tests for event ingestion

from __future__ import annotations

import pytest

async def _register(client, email="ing@test.com"):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secure-pass-1",
            "full_name": "Ing",
            "organization_name": f"Ing Org {email}",
        },
    )
    return resp.json()

@pytest.mark.asyncio
async def test_create_api_key_and_ingest(client):
    auth = await _register(client)
    access = auth["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    keyresp = await client.post(
        "/api/v1/ingest/api-keys",
        json={"name": "Production"},
        headers=headers,
    )
    assert keyresp.status_code == 201
    api_key = keyresp.json()["key"]
    assert api_key.startswith("ak_")

    ingest = await client.post(
        "/api/v1/ingest/events",
        json={
            "event_name": "signup",
            "value": 1.0,
            "properties": {"plan": "free"},
        },
        headers={"X-API-Key": api_key},
    )
    assert ingest.status_code == 202
    assert ingest.json()["accepted"] == 1

@pytest.mark.asyncio
async def test_batch_ingest(client):
    auth = await _register(client, email="batch@test.com")
    access = auth["tokens"]["access_token"]
    keyresp = await client.post(
        "/api/v1/ingest/api-keys",
        json={"name": "Batch"},
        headers={"Authorization": f"Bearer {access}"},
    )
    api_key = keyresp.json()["key"]

    events = [{"event_name": "click", "properties": {"button": "cta"}} for _ in range(50)]
    resp = await client.post(
        "/api/v1/ingest/events/batch",
        json={"events": events},
        headers={"X-API-Key": api_key},
    )
    assert resp.status_code == 202
    assert resp.json()["accepted"] == 50

@pytest.mark.asyncio
async def test_invalid_api_key_rejected(client):
    resp = await client.post(
        "/api/v1/ingest/events",
        json={"event_name": "x"},
        headers={"X-API-Key": "ak_invalid_key"},
    )
    assert resp.status_code == 401
