from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.board import Board, BoardColumn, Card
from app.repositories.board_repository import BoardRepository
from app.schemas.auth import UserOut
from app.schemas.board import (
    BoardOut,
    BoardSummaryOut,
    CardOut,
    ColumnOut,
    CreateBoardRequest,
    CreateCardRequest,
    CreateColumnRequest,
    MoveCardRequest,
    UpdateCardRequest,
)
from app.services.auth_service import user_to_out
from app.services.board_utils import get_card_status_for_column


def card_to_out(card: Card) -> CardOut:
    assignee = None
    if card.assignee:
        assignee = {
            "id": str(card.assignee.id),
            "name": card.assignee.name,
            "email": card.assignee.email,
        }
    return CardOut(
        id=str(card.id),
        title=card.title,
        description=card.description,
        column_id=str(card.column_id),
        position=card.position,
        status=card.status,
        assignee_id=str(card.assignee_id) if card.assignee_id else None,
        assignee=assignee,
    )


def column_to_out(column: BoardColumn) -> ColumnOut:
    cards = sorted(column.cards, key=lambda card: card.position)
    return ColumnOut(
        id=str(column.id),
        title=column.title,
        position=column.position,
        cards=[card_to_out(card) for card in cards],
    )


def board_to_out(board: Board) -> BoardOut:
    columns = sorted(board.columns, key=lambda column: column.position)
    return BoardOut(
        id=str(board.id),
        title=board.title,
        columns=[column_to_out(column) for column in columns],
    )


def board_to_summary(board: Board) -> BoardSummaryOut:
    column_count = len(board.columns)
    card_count = sum(len(column.cards) for column in board.columns)
    return BoardSummaryOut(
        id=str(board.id),
        title=board.title,
        description=board.description or None,
        columnCount=column_count,
        cardCount=card_count,
        updatedAt=board.updated_at.isoformat(),
    )


class BoardService:
    def __init__(self, session: AsyncSession) -> None:
        self.boards = BoardRepository(session)
        self.session = session

    async def _require_access(self, board_id: UUID, user_id: UUID) -> None:
        if not await self.boards.has_access(board_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    async def _require_owner(self, board_id: UUID, user_id: UUID) -> None:
        if not await self.boards.is_owner(board_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only board owner allowed")

    async def list_boards(self, user_id: UUID) -> list[BoardSummaryOut]:
        boards = await self.boards.list_accessible_boards(user_id)
        return [board_to_summary(board) for board in boards]

    async def get_board(self, board_id: UUID, user_id: UUID) -> BoardOut:
        await self._require_access(board_id, user_id)
        board = await self.boards.get_board_with_details(board_id)
        if not board:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        return board_to_out(board)

    async def create_board(self, user_id: UUID, payload: CreateBoardRequest) -> BoardSummaryOut:
        column_titles = [title.strip() for title in payload.columnTitles if title.strip()]
        if not column_titles:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one column is required")

        member_ids: list[UUID] = []
        if payload.memberIds:
            for member_id in payload.memberIds:
                try:
                    member_ids.append(UUID(member_id))
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid member id: {member_id}",
                    ) from exc

        board = await self.boards.create_board(
            user_id=user_id,
            title=payload.title.strip(),
            description=(payload.description or "").strip(),
            column_titles=column_titles,
            member_ids=member_ids,
        )
        await self.session.commit()

        loaded = await self.boards.get_board_with_details(board.id)
        if not loaded:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load board")
        return board_to_summary(loaded)

    async def delete_board(self, board_id: UUID, user_id: UUID) -> None:
        await self._require_owner(board_id, user_id)
        board = await self.boards.get_board(board_id)
        if not board:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        await self.boards.delete_board(board)
        await self.session.commit()

    async def get_members(self, board_id: UUID, user_id: UUID) -> list[UserOut]:
        await self._require_access(board_id, user_id)
        members = await self.boards.get_members(board_id)
        return [user_to_out(member) for member in members]

    async def create_column(self, board_id: UUID, user_id: UUID, payload: CreateColumnRequest) -> ColumnOut:
        await self._require_access(board_id, user_id)
        board = await self.boards.get_board_with_details(board_id)
        if not board:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")

        normalized = payload.title.strip().lower()
        if any(column.title.strip().lower() == normalized for column in board.columns):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Column with this title already exists")

        column = await self.boards.create_column(board_id, payload.title.strip(), len(board.columns))
        await self.boards.touch_board(board_id)
        await self.session.commit()
        await self.session.refresh(column)
        return ColumnOut(id=str(column.id), title=column.title, position=column.position, cards=[])

    async def delete_column(self, column_id: UUID, user_id: UUID) -> None:
        column = await self.boards.get_column_with_board(column_id)
        if not column:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
        await self._require_access(column.board_id, user_id)
        await self.boards.delete_column(column)
        await self.session.commit()

    async def create_card(
        self, column_id: UUID, user_id: UUID, payload: CreateCardRequest
    ) -> CardOut:
        column = await self.boards.get_column_with_board(column_id)
        if not column:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Column not found")
        await self._require_access(column.board_id, user_id)

        assignee_id: UUID | None = None
        if payload.assigneeId:
            try:
                assignee_id = UUID(payload.assigneeId)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assigneeId") from exc

        position = await self.boards.count_cards_in_column(column_id)
        status_value = get_card_status_for_column(column.title)
        card = await self.boards.create_card(
            column_id=column_id,
            title=payload.title.strip(),
            position=position,
            status=status_value,
            assignee_id=assignee_id,
        )
        await self.boards.touch_board(column.board_id)
        await self.session.commit()

        loaded = await self.boards.get_card_with_details(card.id)
        if not loaded:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load card")
        return card_to_out(loaded)

    async def update_card(self, card_id: UUID, user_id: UUID, payload: UpdateCardRequest) -> CardOut:
        card = await self.boards.get_card_with_details(card_id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

        board_id = await self.boards.get_card_board_id(card_id)
        if not board_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        await self._require_access(board_id, user_id)

        assignee_id = ...
        if payload.assigneeId is not None:
            if payload.assigneeId == "":
                assignee_id = None
            else:
                try:
                    assignee_id = UUID(payload.assigneeId)
                except ValueError as exc:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid assigneeId"
                    ) from exc

        updated = await self.boards.update_card(
            card,
            title=payload.title.strip() if payload.title is not None else None,
            description=payload.description.strip() if payload.description is not None else None,
            assignee_id=assignee_id,
        )
        await self.boards.touch_board(board_id)
        await self.session.commit()
        await self.session.refresh(updated)
        reloaded = await self.boards.get_card_with_details(card_id)
        return card_to_out(reloaded)  # type: ignore[arg-type]

    async def delete_card(self, card_id: UUID, user_id: UUID) -> None:
        card = await self.boards.get_card(card_id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

        board_id = await self.boards.get_card_board_id(card_id)
        if not board_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        await self._require_access(board_id, user_id)
        await self.boards.delete_card(card)
        await self.session.commit()

    async def move_card(self, card_id: UUID, user_id: UUID, payload: MoveCardRequest) -> None:
        card = await self.boards.get_card_with_details(card_id)
        if not card:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")

        source_column = card.column
        target_column = await self.boards.get_column_with_board(UUID(payload.targetColumnId))
        if not target_column:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target column not found")

        if source_column.board_id != target_column.board_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Columns belong to different boards")

        await self._require_access(source_column.board_id, user_id)

        original_source_cards = await self.boards.list_cards_in_column(source_column.id)
        source_index = next(
            (index for index, item in enumerate(original_source_cards) if item.id == card.id),
            -1,
        )
        insert_index = payload.targetIndex

        if source_column.id == target_column.id:
            remaining = [item for item in original_source_cards if item.id != card.id]
            if source_index >= 0 and source_index < insert_index:
                insert_index = max(0, insert_index - 1)
            remaining.insert(min(insert_index, len(remaining)), card)
            card.column_id = target_column.id
            card.status = get_card_status_for_column(target_column.title)
            for index, item in enumerate(remaining):
                item.position = index
        else:
            source_cards = [item for item in original_source_cards if item.id != card.id]
            target_cards = await self.boards.list_cards_in_column(target_column.id)
            card.column_id = target_column.id
            card.status = get_card_status_for_column(target_column.title)
            target_cards.insert(min(insert_index, len(target_cards)), card)
            for index, item in enumerate(source_cards):
                item.position = index
            for index, item in enumerate(target_cards):
                item.position = index

        await self.boards.touch_board(source_column.board_id)
        await self.session.commit()
