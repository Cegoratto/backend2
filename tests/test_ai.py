import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_ask_endpoint(client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    async def fake_call_openrouter(self, messages):
        return "DeepSeek answer"

    monkeypatch.setattr(
        "app.services.ai_service.AiService._call_openrouter",
        fake_call_openrouter,
    )

    response = await client.post("/api/ask", json={"question": "What is AI?"})
    assert response.status_code == 200
    assert response.json() == {"answer": "DeepSeek answer"}


@pytest.mark.asyncio
async def test_decompose_and_assign(client: AsyncClient, auth_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch):
    board_response = await client.post(
        "/api/boards",
        headers=auth_headers,
        json={"title": "AI Board", "columnTitles": ["Todo", "Done"]},
    )
    board_id = board_response.json()["id"]
    me = (await client.get("/api/auth/me", headers=auth_headers)).json()

    async def fake_call_openrouter(self, messages):
        return (
            '{"subtasks":[{"title":"Build API","description":"Implement endpoints","role":"Frontend Developer"}]}'
        )

    monkeypatch.setattr(
        "app.services.ai_service.AiService._call_openrouter",
        fake_call_openrouter,
    )

    response = await client.post(
        "/api/tasks/decompose-and-assign",
        headers=auth_headers,
        json={
            "boardId": board_id,
            "globalTask": "Launch MVP",
            "users": [
                {
                    "id": me["id"],
                    "name": me["name"],
                    "role": "Frontend Developer",
                }
            ],
        },
    )
    assert response.status_code == 200
    tasks = response.json()
    assert len(tasks) == 1
    assert tasks[0]["title"] == "Build API"
    assert tasks[0]["assigneeId"] == me["id"]
