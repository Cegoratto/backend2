from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.board import ColumnOut, CreateColumnRequest
from app.services.board_service import BoardService

router = APIRouter(tags=["columns"])


@router.post("/api/boards/{board_id}/columns", response_model=ColumnOut, status_code=status.HTTP_201_CREATED)
async def create_column(
    board_id: UUID,
    payload: CreateColumnRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> ColumnOut:
    return await BoardService(session).create_column(board_id, current_user.id, payload)


@router.delete("/api/columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_column(
    column_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await BoardService(session).delete_column(column_id, current_user.id)
