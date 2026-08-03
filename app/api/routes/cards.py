from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.board import CardOut, CreateCardRequest, MoveCardRequest, UpdateCardRequest
from app.services.board_service import BoardService

router = APIRouter(tags=["cards"])


@router.post("/api/columns/{column_id}/cards", response_model=CardOut, status_code=status.HTTP_201_CREATED)
async def create_card(
    column_id: UUID,
    payload: CreateCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CardOut:
    return await BoardService(session).create_card(column_id, current_user.id, payload)


@router.patch("/api/cards/{card_id}", response_model=CardOut)
async def update_card(
    card_id: UUID,
    payload: UpdateCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> CardOut:
    return await BoardService(session).update_card(card_id, current_user.id, payload)


@router.delete("/api/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(
    card_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await BoardService(session).delete_card(card_id, current_user.id)


@router.post("/api/cards/{card_id}/move", status_code=status.HTTP_204_NO_CONTENT)
async def move_card(
    card_id: UUID,
    payload: MoveCardRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await BoardService(session).move_card(card_id, current_user.id, payload)
