from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserOut
from app.schemas.board import BoardOut, BoardSummaryOut, CreateBoardRequest
from app.services.board_service import BoardService

router = APIRouter(prefix="/api/boards", tags=["boards"])


@router.get("", response_model=list[BoardSummaryOut])
async def list_boards(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[BoardSummaryOut]:
    return await BoardService(session).list_boards(current_user.id)


@router.get("/{board_id}", response_model=BoardOut)
async def get_board(
    board_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BoardOut:
    return await BoardService(session).get_board(board_id, current_user.id)


@router.post("", response_model=BoardSummaryOut, status_code=status.HTTP_201_CREATED)
async def create_board(
    payload: CreateBoardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BoardSummaryOut:
    return await BoardService(session).create_board(current_user.id, payload)


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_board(
    board_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await BoardService(session).delete_board(board_id, current_user.id)


@router.get("/{board_id}/members", response_model=list[UserOut])
async def get_board_members(
    board_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[UserOut]:
    return await BoardService(session).get_members(board_id, current_user.id)
