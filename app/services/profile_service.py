from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import UpdateTeamRoleRequest, UserOut
from app.services.auth_service import user_to_out


class ProfileService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.session = session

    async def list_profiles(self) -> list[UserOut]:
        users = await self.users.list_all()
        return [user_to_out(user) for user in users]

    async def update_team_role(self, current_user: User, payload: UpdateTeamRoleRequest) -> UserOut:
        updated = await self.users.update_team_role(current_user, payload.teamRole)
        await self.session.commit()
        await self.session.refresh(updated)
        return user_to_out(updated)
