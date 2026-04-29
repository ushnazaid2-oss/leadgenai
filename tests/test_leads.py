"""
Test leads endpoints — CRUD, CSV import, filtering.
"""
import pytest


@pytest.mark.asyncio
async def test_create_lead(client, auth_headers):
    response = await client.post("/api/leads/", json={
        "name": "Test Lead", "email": "lead@test.com",
        "company": "TestCorp", "niche": "SaaS"
    }, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Lead"
    assert data["status"] == "new"


@pytest.mark.asyncio
async def test_duplicate_lead(client, auth_headers):
    await client.post("/api/leads/", json={
        "name": "Dup Lead", "email": "dup_lead@test.com"
    }, headers=auth_headers)
    response = await client.post("/api/leads/", json={
        "name": "Dup Lead 2", "email": "dup_lead@test.com"
    }, headers=auth_headers)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_leads(client, auth_headers):
    await client.post("/api/leads/", json={
        "name": "List Lead", "email": "list@test.com"
    }, headers=auth_headers)
    response = await client.get("/api/leads/", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert len(data["leads"]) >= 1


@pytest.mark.asyncio
async def test_update_lead(client, auth_headers):
    create = await client.post("/api/leads/", json={
        "name": "Update Me", "email": "update@test.com"
    }, headers=auth_headers)
    lead_id = create.json()["id"]
    response = await client.put(f"/api/leads/{lead_id}", json={
        "status": "interested", "is_hot_lead": True
    }, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["status"] == "interested"
    assert response.json()["is_hot_lead"] == True


@pytest.mark.asyncio
async def test_delete_lead(client, auth_headers):
    create = await client.post("/api/leads/", json={
        "name": "Delete Me", "email": "delete@test.com"
    }, headers=auth_headers)
    lead_id = create.json()["id"]
    response = await client.delete(f"/api/leads/{lead_id}", headers=auth_headers)
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_csv_import(client, auth_headers):
    csv_content = b"name,email,company,phone,niche\nCSV Lead,csv@test.com,CSVCorp,+14155551234,SaaS"
    response = await client.post(
        "/api/leads/import/csv",
        files={"file": ("test.csv", csv_content, "text/csv")},
        headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["imported"] == 1
