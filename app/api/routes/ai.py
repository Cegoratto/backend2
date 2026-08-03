from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import AskRequest, AskResponse, DecomposeRequest, DecomposedTaskOut
from app.services.ai_service import AiService

router = APIRouter(prefix="/api", tags=["ai"])


@router.post("/ask", response_model=AskResponse)
async def ask(
    payload: AskRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AskResponse:
    return await AiService(session).ask(payload)


@router.post("/tasks/decompose-and-assign", response_model=list[DecomposedTaskOut])
async def decompose_and_assign(
    payload: DecomposeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[DecomposedTaskOut]:
    return await AiService(session).decompose_and_assign(payload, current_user.id)
