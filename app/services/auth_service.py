from uuid import UUID

import httpx
from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, GoogleAuthRequest, LoginRequest, RegisterRequest, UserOut


def user_to_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        name=user.name,
        email=user.email,
        teamRole=user.team_role,
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.session = session

    async def register(self, payload: RegisterRequest) -> AuthResponse:
        existing = await self.users.get_by_email(payload.email)
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

        user = await self.users.create(
            email=payload.email,
            password_hash=hash_password(payload.password),
            name=payload.name.strip(),
            team_role=payload.teamRole,
        )
        await self.session.commit()
        await self.session.refresh(user)

        token = create_access_token(user.id)
        return AuthResponse(access_token=token, user=user_to_out(user))

    async def login(self, payload: LoginRequest) -> AuthResponse:
        user = await self.users.get_by_email(payload.email)
        if not user or user.password_hash is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_access_token(user.id)
        return AuthResponse(access_token=token, user=user_to_out(user))

    async def google_login(self, payload: GoogleAuthRequest) -> AuthResponse:
        settings = get_settings()
        if not settings.google_client_id:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Google sign-in is not configured",
            )

        if payload.idToken:
            id_info = self._verify_google_id_token(payload.idToken, settings.google_client_id)
        else:
            id_info = await self._fetch_google_userinfo(payload.accessToken or "")

        return await self._login_google_user(id_info)

    def _verify_google_id_token(self, raw_id_token: str, client_id: str) -> dict:
        try:
            return id_token.verify_oauth2_token(
                raw_id_token,
                requests.Request(),
                client_id,
            )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
            )

    async def _fetch_google_userinfo(self, access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token",
            )

        userinfo = response.json()
        return {
            "email": userinfo.get("email"),
            "email_verified": userinfo.get("verified_email", False),
            "name": userinfo.get("name"),
            "given_name": userinfo.get("given_name"),
        }

    async def _login_google_user(self, id_info: dict) -> AuthResponse:
        email = id_info.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google account email is missing",
            )

        if not id_info.get("email_verified", False):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google email is not verified",
            )

        name = id_info.get("name") or id_info.get("given_name") or email.split("@")[0]

        user = await self.users.get_by_email(email)
        if not user:
            user = await self.users.create_oauth_user(email=email, name=name)
            await self.session.commit()
            await self.session.refresh(user)

        token = create_access_token(user.id)
        return AuthResponse(access_token=token, user=user_to_out(user))

    async def get_me(self, user_id: UUID) -> UserOut:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user_to_out(user)
