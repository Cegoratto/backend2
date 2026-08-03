from pydantic import BaseModel, Field


class CardAssigneeOut(BaseModel):
    id: str
    name: str
    email: str


class CardOut(BaseModel):
    id: str
    title: str
    description: str
    column_id: str
    position: int
    status: str
    assignee_id: str | None = None
    assignee: CardAssigneeOut | None = None


class ColumnOut(BaseModel):
    id: str
    title: str
    position: int
    cards: list[CardOut] = []


class BoardOut(BaseModel):
    id: str
    title: str
    columns: list[ColumnOut]


class BoardSummaryOut(BaseModel):
    id: str
    title: str
    description: str | None = None
    columnCount: int
    cardCount: int
    updatedAt: str


class CreateBoardRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = ""
    columnTitles: list[str] = Field(min_length=1)
    memberIds: list[str] | None = None


class CreateColumnRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class CreateCardRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    assigneeId: str | None = None


class UpdateCardRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assigneeId: str | None = None


class MoveCardRequest(BaseModel):
    targetColumnId: str
    targetIndex: int = Field(ge=0)
