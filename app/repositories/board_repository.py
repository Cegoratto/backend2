from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.board import Board, BoardColumn, BoardMember, Card
from app.models.user import User


class BoardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_accessible_boards(self, user_id: UUID) -> list[Board]:
        member_board_ids = select(BoardMember.board_id).where(BoardMember.user_id == user_id)
        result = await self.session.execute(
            select(Board)
            .where(or_(Board.user_id == user_id, Board.id.in_(member_board_ids)))
            .options(selectinload(Board.columns).selectinload(BoardColumn.cards))
            .order_by(Board.updated_at.desc())
        )
        return list(result.scalars().unique().all())

    async def get_board_with_details(self, board_id: UUID) -> Board | None:
        result = await self.session.execute(
            select(Board)
            .where(Board.id == board_id)
            .options(
                selectinload(Board.columns)
                .selectinload(BoardColumn.cards)
                .selectinload(Card.assignee)
            )
        )
        return result.scalar_one_or_none()

    async def get_board(self, board_id: UUID) -> Board | None:
        return await self.session.get(Board, board_id)

    async def create_board(
        self,
        user_id: UUID,
        title: str,
        description: str,
        column_titles: list[str],
        member_ids: list[UUID],
    ) -> Board:
        board = Board(user_id=user_id, title=title, description=description)
        self.session.add(board)
        await self.session.flush()

        for index, column_title in enumerate(column_titles):
            self.session.add(
                BoardColumn(board_id=board.id, title=column_title.strip(), position=index)
            )

        for member_id in member_ids:
            if member_id != user_id:
                self.session.add(BoardMember(board_id=board.id, user_id=member_id))

        await self.session.flush()
        return board

    async def delete_board(self, board: Board) -> None:
        await self.session.delete(board)

    async def touch_board(self, board_id: UUID) -> None:
        board = await self.session.get(Board, board_id)
        if board:
            board.updated_at = datetime.now(UTC)
            await self.session.flush()

    async def has_access(self, board_id: UUID, user_id: UUID) -> bool:
        board = await self.session.get(Board, board_id)
        if not board:
            return False
        if board.user_id == user_id:
            return True
        result = await self.session.execute(
            select(BoardMember.id).where(
                BoardMember.board_id == board_id, BoardMember.user_id == user_id
            )
        )
        return result.scalar_one_or_none() is not None

    async def is_owner(self, board_id: UUID, user_id: UUID) -> bool:
        board = await self.session.get(Board, board_id)
        return board is not None and board.user_id == user_id

    async def get_members(self, board_id: UUID) -> list[User]:
        board = await self.session.get(Board, board_id)
        if not board:
            return []

        member_ids_result = await self.session.execute(
            select(BoardMember.user_id).where(BoardMember.board_id == board_id)
        )
        user_ids = {board.user_id, *member_ids_result.scalars().all()}
        result = await self.session.execute(select(User).where(User.id.in_(user_ids)).order_by(User.name))
        return list(result.scalars().all())

    async def get_column(self, column_id: UUID) -> BoardColumn | None:
        return await self.session.get(BoardColumn, column_id)

    async def get_column_with_board(self, column_id: UUID) -> BoardColumn | None:
        result = await self.session.execute(
            select(BoardColumn)
            .where(BoardColumn.id == column_id)
            .options(selectinload(BoardColumn.board))
        )
        return result.scalar_one_or_none()

    async def list_columns(self, board_id: UUID) -> list[BoardColumn]:
        result = await self.session.execute(
            select(BoardColumn)
            .where(BoardColumn.board_id == board_id)
            .order_by(BoardColumn.position)
        )
        return list(result.scalars().all())

    async def create_column(self, board_id: UUID, title: str, position: int) -> BoardColumn:
        column = BoardColumn(board_id=board_id, title=title, position=position)
        self.session.add(column)
        await self.session.flush()
        return column

    async def delete_column(self, column: BoardColumn) -> None:
        board_id = column.board_id
        await self.session.delete(column)
        await self.session.flush()

        result = await self.session.execute(
            select(BoardColumn)
            .where(BoardColumn.board_id == board_id)
            .order_by(BoardColumn.position)
        )
        for index, remaining in enumerate(result.scalars().all()):
            remaining.position = index
        await self.session.flush()
        await self.touch_board(board_id)

    async def get_card(self, card_id: UUID) -> Card | None:
        return await self.session.get(Card, card_id)

    async def get_card_with_details(self, card_id: UUID) -> Card | None:
        result = await self.session.execute(
            select(Card)
            .where(Card.id == card_id)
            .options(selectinload(Card.assignee), selectinload(Card.column))
        )
        return result.scalar_one_or_none()

    async def count_cards_in_column(self, column_id: UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Card).where(Card.column_id == column_id)
        )
        return int(result.scalar_one())

    async def create_card(
        self,
        column_id: UUID,
        title: str,
        position: int,
        status: str,
        assignee_id: UUID | None = None,
        description: str = "",
    ) -> Card:
        card = Card(
            column_id=column_id,
            title=title,
            description=description,
            position=position,
            status=status,
            assignee_id=assignee_id,
        )
        self.session.add(card)
        await self.session.flush()
        return card

    async def update_card(
        self,
        card: Card,
        title: str | None = None,
        description: str | None = None,
        assignee_id: UUID | None = ...,  # type: ignore[assignment]
    ) -> Card:
        if title is not None:
            card.title = title
        if description is not None:
            card.description = description
        if assignee_id is not ...:
            card.assignee_id = assignee_id
        await self.session.flush()
        return card

    async def delete_card(self, card: Card) -> None:
        column = await self.session.get(BoardColumn, card.column_id)
        board_id = column.board_id if column else None
        await self.session.delete(card)
        await self.session.flush()
        if board_id:
            await self.touch_board(board_id)

    async def list_cards_in_column(self, column_id: UUID) -> list[Card]:
        result = await self.session.execute(
            select(Card).where(Card.column_id == column_id).order_by(Card.position)
        )
        return list(result.scalars().all())

    async def get_max_position_in_column(self, column_id: UUID) -> int:
        result = await self.session.execute(
            select(func.max(Card.position)).where(Card.column_id == column_id)
        )
        value = result.scalar_one()
        return int(value) if value is not None else -1

    async def get_card_board_id(self, card_id: UUID) -> UUID | None:
        result = await self.session.execute(
            select(BoardColumn.board_id)
            .join(Card, Card.column_id == BoardColumn.id)
            .where(Card.id == card_id)
        )
        return result.scalar_one_or_none()
