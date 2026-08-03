from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_all(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.name))
        return list(result.scalars().all())

    async def create(self, email: str, password_hash: str, name: str, team_role: str) -> User:
        user = User(email=email, password_hash=password_hash, name=name, team_role=team_role)
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_team_role(self, user: User, team_role: str) -> User:
        user.team_role = team_role
        await self.session.flush()
        return user
