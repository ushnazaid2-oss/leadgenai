"""
Test email endpoints — account creation, stats.
"""
import pytest


@pytest.mark.asyncio
async def test_email_stats(client, auth_headers):
    response = await client.get("/api/email/stats", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_sent" in data
    assert "open_rate" in data


@pytest.mark.asyncio
async def test_email_accounts_list(client, auth_headers):
    response = await client.get("/api/email/accounts", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_add_email_account(client, auth_headers):
    response = await client.post("/api/email/accounts", json={
        "name": "Test Sender", "email": "sender@test.com",
        "provider": "gmail", "username": "sender@test.com",
        "password": "app-password"
    }, headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["email"] == "sender@test.com"
