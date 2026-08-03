import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    assert response.text == "Hello World!"


@pytest.mark.asyncio
async def test_register_and_login(client: AsyncClient):
    register_response = await client.post(
        "/api/auth/register",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "secret123",
            "teamRole": "Backend Developer",
        },
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "bob@example.com"

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "bob@example.com", "password": "secret123"},
    )
    assert login_response.status_code == 200
    assert "access_token" in login_response.json()


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    response = await client.post(
        "/api/auth/login",
        json={"email": "missing@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client: AsyncClient):
    response = await client.get("/api/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user(client: AsyncClient, auth_headers: dict[str, str]):
    response = await client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "alice@example.com"
