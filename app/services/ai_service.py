import json
import re
from uuid import UUID

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.repositories.board_repository import BoardRepository
from app.schemas.ai import AskRequest, AskResponse, DecomposeRequest, DecomposedTaskOut
from app.services.board_utils import get_card_status_for_column

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "deepseek/deepseek-v4-flash"


def parse_json_from_text(text: str) -> dict:
    trimmed = text.strip()
    if not trimmed:
        raise ValueError("Model returned an empty response")

    fenced_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", trimmed, re.IGNORECASE)
    candidate = fenced_match.group(1).strip() if fenced_match else trimmed

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            return json.loads(candidate[start : end + 1])
        raise ValueError("Model did not return valid JSON") from None


def extract_answer(content: str | list | None) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "".join(parts).strip()
    return ""


def build_decomposition_messages(global_task: str, users: list[dict[str, str]]) -> list[dict[str, str]]:
    available_roles = sorted({user["role"] for user in users})
    team_context = "\n".join(f"{user['name']} ({user['id']}) - {user['role']}" for user in users)
    return [
        {
            "role": "system",
            "content": "You are a technical project decomposition assistant. Respond ONLY with valid JSON and no extra text.",
        },
        {
            "role": "user",
            "content": "\n".join(
                [
                    "Split the global task into small practical subtasks and assign each subtask to one of the available roles.",
                    "",
                    f"Global task: {global_task}",
                    "",
                    f"Available roles: {', '.join(available_roles)}",
                    "Team members:",
                    team_context,
                    "",
                    'Return strict JSON in this exact format: {"subtasks":[{"title":"...","description":"...","role":"..."}]}',
                    "Rules:",
                    "- role must be one of the available roles exactly.",
                    "- title should be concise and actionable.",
                    "- description should contain concrete implementation details.",
                ]
            ),
        },
    ]


class AiService:
    def __init__(self, session: AsyncSession) -> None:
        self.boards = BoardRepository(session)
        self.session = session
        self.settings = get_settings()

    async def _call_openrouter(self, messages: list[dict[str, str]]) -> str:
        if not self.settings.openrouter_api_key.strip():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENROUTER_API_KEY is not configured",
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {self.settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                json={"model": OPENROUTER_MODEL, "messages": messages},
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="OpenRouter request failed") from exc

        if not response.is_success:
            message = payload.get("error", {}).get("message") if isinstance(payload, dict) else None
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=message or "OpenRouter request failed",
            )

        answer = extract_answer(payload.get("choices", [{}])[0].get("message", {}).get("content"))
        if not answer:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Model returned an empty response")
        return answer

    async def ask(self, payload: AskRequest) -> AskResponse:
        answer = await self._call_openrouter([{"role": "user", "content": payload.question.strip()}])
        return AskResponse(answer=answer)

    async def decompose_and_assign(self, payload: DecomposeRequest, user_id: UUID) -> list[DecomposedTaskOut]:
        try:
            board_id = UUID(payload.boardId)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid boardId") from exc

        if not await self.boards.has_access(board_id, user_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

        users = [
            {"id": user.id.strip(), "name": user.name.strip(), "role": user.role.strip()}
            for user in payload.users
            if user.id.strip() and user.name.strip() and user.role.strip()
        ]
        if not users:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Field 'users' must be a non-empty array of { id, name, role } objects",
            )

        answer = await self._call_openrouter(build_decomposition_messages(payload.globalTask.strip(), users))
        try:
            parsed = parse_json_from_text(answer)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

        subtasks_raw = parsed.get("subtasks") if isinstance(parsed, dict) else None
        if not isinstance(subtasks_raw, list) or not subtasks_raw:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Model returned invalid subtasks format")

        subtasks = []
        for item in subtasks_raw:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            description = str(item.get("description", "")).strip()
            role = str(item.get("role", "")).strip()
            if title and description and role:
                subtasks.append({"title": title, "description": description, "role": role})

        if not subtasks:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Model returned invalid subtasks format")

        columns = await self.boards.list_columns(board_id)
        if not columns:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board or columns were not found")

        todo_column = next(
            (column for column in columns if column.title.strip().lower() == "todo"),
            columns[0],
        )
        next_position = await self.boards.get_max_position_in_column(todo_column.id) + 1

        created: list[DecomposedTaskOut] = []
        role_to_user = {user["role"].lower(): user["id"] for user in users}

        for subtask in subtasks:
            assignee_id = role_to_user.get(subtask["role"].lower())
            card = await self.boards.create_card(
                column_id=todo_column.id,
                title=subtask["title"],
                description=subtask["description"],
                position=next_position,
                status="todo",
                assignee_id=UUID(assignee_id) if assignee_id else None,
            )
            next_position += 1
            created.append(
                DecomposedTaskOut(
                    id=str(card.id),
                    boardId=str(board_id),
                    columnId=str(todo_column.id),
                    title=card.title,
                    description=card.description,
                    role=subtask["role"],
                    assigneeId=assignee_id,
                    status=card.status,
                    position=card.position,
                )
            )

        await self.boards.touch_board(board_id)
        await self.session.commit()
        return created
