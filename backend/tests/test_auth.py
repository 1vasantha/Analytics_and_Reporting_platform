# Tests for the auth endpoints.

from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_register_creates_org_and_user(client):
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "owner@test.com",
            "password": "secure-pass-1",
            "full_name": "Owner User",
            "organization_name": "Test Corp",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user"]["email"] == "owner@test.com"
    assert body["user"]["role"] == "owner"
    assert body["organization"]["name"] == "Test Corp"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]


@pytest.mark.asyncio
async def test_register_duplicate_email_rejected(client):
    payload = {
        "email": "dup@test.com",
        "password": "secure-pass-1",
        "full_name": "A",
        "organization_name": "First Org",
    }
    r1 = await client.post("/api/v1/auth/register", json=payload)
    assert r1.status_code == 201

    payload["organization_name"] = "Second Org"
    r2 = await client.post("/api/v1/auth/register", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@test.com",
            "password": "secure-pass-1",
            "full_name": "L",
            "organization_name": "L Org",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login@test.com", "password": "secure-pass-1"},
    )
    assert resp.status_code == 200
    assert resp.json()["tokens"]["access_token"]


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "wrong@test.com",
            "password": "secure-pass-1",
            "full_name": "W",
            "organization_name": "W Org",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrong@test.com", "password": "wrong-password"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_token(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_authenticated_user(client):
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "me@test.com",
            "password": "secure-pass-1",
            "full_name": "Me",
            "organization_name": "Me Org",
        },
    )
    access = reg.json()["tokens"]["access_token"]
    resp = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@test.com"
