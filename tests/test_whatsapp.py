"""
Test WhatsApp endpoints.
"""
import pytest


@pytest.mark.asyncio
async def test_whatsapp_logs(client, auth_headers):
    response = await client.get("/api/whatsapp/logs", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
