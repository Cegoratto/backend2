from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UpdateTeamRoleRequest, UserOut
from app.services.profile_service import ProfileService

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


@router.get("", response_model=list[UserOut])
async def list_profiles(
    _: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    return await ProfileService(session).list_profiles()


@router.patch("/me", response_model=UserOut)
async def update_my_profile(
    payload: UpdateTeamRoleRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserOut:
    return await ProfileService(session).update_team_role(current_user, payload)
