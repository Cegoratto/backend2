from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(min_length=1)


class AskResponse(BaseModel):
    answer: str


class DecomposeUserInput(BaseModel):
    id: str
    name: str
    role: str


class DecomposeRequest(BaseModel):
    boardId: str
    globalTask: str = Field(min_length=1)
    users: list[DecomposeUserInput] = Field(min_length=1)


class DecomposedTaskOut(BaseModel):
    id: str
    boardId: str
    columnId: str
    title: str
    description: str
    role: str
    assigneeId: str | None
    status: str
    position: int
