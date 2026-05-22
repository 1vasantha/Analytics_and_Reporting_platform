# Tests for dashboards and widgets

from __future__ import annotations

import pytest


async def _register(client, email="dash@test.com"):
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "secure-pass-1",
            "full_name": "Dash",
            "organization_name": f"Dash Org {email}",
        },
    )
    return r.json()


@pytest.mark.asyncio
async def test_create_and_list_dashboard(client):
    auth = await _register(client)
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/dashboards",
        json={"name": "My Dashboard", "refresh_interval": 30},
        headers=headers,
    )
    assert resp.status_code == 201
    dash = resp.json()
    assert dash["name"] == "My Dashboard"
    assert dash["widgets"] == []

    lst = await client.get("/api/v1/dashboards", headers=headers)
    assert lst.status_code == 200
    assert len(lst.json()) == 1


@pytest.mark.asyncio
async def test_add_widget(client):
    auth = await _register(client, email="widget@test.com")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    dash_resp = await client.post(
        "/api/v1/dashboards",
        json={"name": "W Dashboard"},
        headers=headers,
    )
    dash_id = dash_resp.json()["id"]

    widget_payload = {
        "title": "Signups",
        "chart_type": "kpi",
        "query_config": {
            "event_name": "signup",
            "aggregation": "count",
            "time_range": {"relative": "24h"},
        },
        "layout": {"x": 0, "y": 0, "w": 4, "h": 2},
    }
    resp = await client.post(
        f"/api/v1/dashboards/{dash_id}/widgets",
        json=widget_payload,
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "Signups"

    detail = await client.get(f"/api/v1/dashboards/{dash_id}", headers=headers)
    assert len(detail.json()["widgets"]) == 1


@pytest.mark.asyncio
async def test_ad_hoc_query(client):
    auth = await _register(client, email="query@test.com")
    headers = {"Authorization": f"Bearer {auth['tokens']['access_token']}"}

    resp = await client.post(
        "/api/v1/dashboards/query",
        json={
            "aggregation": "count",
            "time_range": {"relative": "24h"},
        },
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "points" in body
    assert body["total"] == 0 


@pytest.mark.asyncio
async def test_cross_org_isolation(client):
    a = await _register(client, email="a@iso.com")
    b = await _register(client, email="b@iso.com")
    h_a = {"Authorization": f"Bearer {a['tokens']['access_token']}"}
    h_b = {"Authorization": f"Bearer {b['tokens']['access_token']}"}

    dash = await client.post(
        "/api/v1/dashboards",
        json={"name": "A's Dashboard"},
        headers=h_a,
    )
    dash_id = dash.json()["id"]

    resp = await client.get(f"/api/v1/dashboards/{dash_id}", headers=h_b)
    assert resp.status_code == 404
