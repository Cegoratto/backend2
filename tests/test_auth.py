import pytest
from httpx import AsyncClient
from unittest.mock import patch


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


@pytest.mark.asyncio
async def test_google_auth_creates_user(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_id_info = {
        "email": "google@example.com",
        "email_verified": True,
        "name": "Google User",
    }

    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=mock_id_info):
        response = await client.post(
            "/api/auth/google",
            json={"idToken": "valid-google-id-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "google@example.com"
    assert body["user"]["name"] == "Google User"
    assert body["user"]["teamRole"] is None
    assert "access_token" in body


@pytest.mark.asyncio
async def test_google_auth_logs_in_existing_user(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

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

    mock_id_info = {
        "email": "bob@example.com",
        "email_verified": True,
        "name": "Bob",
    }

    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=mock_id_info):
        response = await client.post(
            "/api/auth/google",
            json={"idToken": "valid-google-id-token"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == "bob@example.com"
    assert body["user"]["teamRole"] == "Backend Developer"


@pytest.mark.asyncio
async def test_google_auth_rejects_unverified_email(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_id_info = {
        "email": "unverified@example.com",
        "email_verified": False,
        "name": "Unverified",
    }

    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=mock_id_info):
        response = await client.post(
            "/api/auth/google",
            json={"idToken": "valid-google-id-token"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_user_cannot_login_with_password(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-google-client-id.apps.googleusercontent.com")
    from app.core.config import get_settings

    get_settings.cache_clear()

    mock_id_info = {
        "email": "oauth-only@example.com",
        "email_verified": True,
        "name": "OAuth User",
    }

    with patch("app.services.auth_service.id_token.verify_oauth2_token", return_value=mock_id_info):
        google_response = await client.post(
            "/api/auth/google",
            json={"idToken": "valid-google-id-token"},
        )
    assert google_response.status_code == 200

    login_response = await client.post(
        "/api/auth/login",
        json={"email": "oauth-only@example.com", "password": "anypassword"},
    )
    assert login_response.status_code == 401
