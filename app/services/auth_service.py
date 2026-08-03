from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut


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
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        token = create_access_token(user.id)
        return AuthResponse(access_token=token, user=user_to_out(user))

    async def get_me(self, user_id: UUID) -> UserOut:
        user = await self.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        return user_to_out(user)
