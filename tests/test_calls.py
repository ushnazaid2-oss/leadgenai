"""
Test calls endpoints.
"""
import pytest


@pytest.mark.asyncio
async def test_call_stats(client, auth_headers):
    response = await client.get("/api/calls/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "conversion_rate" in data


@pytest.mark.asyncio
async def test_call_logs(client, auth_headers):
    response = await client.get("/api/calls/logs", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
