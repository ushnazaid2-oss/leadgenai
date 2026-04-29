"""
Test auth endpoints — register, login, token refresh, and protected routes.
"""
import pytest


@pytest.mark.asyncio
async def test_register(client):
    response = await client.post("/api/auth/register", json={
        "username": "newuser", "email": "new@test.com", "password": "secure123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["username"] == "newuser"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    await client.post("/api/auth/register", json={
        "username": "dupuser", "email": "dup@test.com", "password": "secure123"
    })
    response = await client.post("/api/auth/register", json={
        "username": "dupuser", "email": "dup2@test.com", "password": "secure123"
    })
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/api/auth/register", json={
        "username": "loginuser", "email": "login@test.com", "password": "secure123"
    })
    response = await client.post("/api/auth/login", json={
        "username": "loginuser", "password": "secure123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/api/auth/register", json={
        "username": "wrongpw", "email": "wrong@test.com", "password": "secure123"
    })
    response = await client.post("/api/auth/login", json={
        "username": "wrongpw", "password": "wrongpassword"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_without_auth(client):
    response = await client.get("/api/leads/")
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_me(client, auth_headers):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"
