import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_board_crud_and_access(client: AsyncClient, auth_headers: dict[str, str]):
    create_response = await client.post(
        "/api/boards",
        headers=auth_headers,
        json={
            "title": "Sprint Board",
            "description": "Test board",
            "columnTitles": ["Todo", "In Progress", "Done"],
        },
    )
    assert create_response.status_code == 201
    board_id = create_response.json()["id"]

    list_response = await client.get("/api/boards", headers=auth_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = await client.get(f"/api/boards/{board_id}", headers=auth_headers)
    assert detail_response.status_code == 200
    assert len(detail_response.json()["columns"]) == 3

    delete_response = await client.delete(f"/api/boards/{board_id}", headers=auth_headers)
    assert delete_response.status_code == 204


@pytest.mark.asyncio
async def test_create_card_and_move(client: AsyncClient, auth_headers: dict[str, str]):
    board_response = await client.post(
        "/api/boards",
        headers=auth_headers,
        json={"title": "Move Board", "columnTitles": ["Todo", "Done"]},
    )
    board_id = board_response.json()["id"]
    board = (await client.get(f"/api/boards/{board_id}", headers=auth_headers)).json()
    todo_column_id = board["columns"][0]["id"]
    done_column_id = board["columns"][1]["id"]

    card_response = await client.post(
        f"/api/columns/{todo_column_id}/cards",
        headers=auth_headers,
        json={"title": "First task"},
    )
    assert card_response.status_code == 201
    card_id = card_response.json()["id"]
    assert card_response.json()["status"] == "todo"

    move_response = await client.post(
        f"/api/cards/{card_id}/move",
        headers=auth_headers,
        json={"targetColumnId": done_column_id, "targetIndex": 0},
    )
    assert move_response.status_code == 204

    updated_board = (await client.get(f"/api/boards/{board_id}", headers=auth_headers)).json()
    done_cards = updated_board["columns"][1]["cards"]
    assert len(done_cards) == 1
    assert done_cards[0]["status"] == "done"
