from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

import app.main as todo_app


client = TestClient(todo_app.app)


def setup_function() -> None:
    todo_app.todos.clear()
    todo_app.next_todo_id = 1


def test_health_check() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_and_list_todo() -> None:
    create_response = client.post("/todos", json={"title": "DevOps 실습"})
    list_response = client.get("/todos")

    assert create_response.status_code == 201
    assert create_response.json() == {"id": 1, "title": "DevOps 실습", "completed": False}
    assert list_response.status_code == 200
    assert list_response.json() == [{"id": 1, "title": "DevOps 실습", "completed": False}]


def test_complete_todo() -> None:
    client.post("/todos", json={"title": "테스트"})

    response = client.patch("/todos/1/complete")

    assert response.status_code == 200
    assert response.json()["completed"] is True


def test_delete_todo() -> None:
    client.post("/todos", json={"title": "삭제"})

    delete_response = client.delete("/todos/1")
    list_response = client.get("/todos")

    assert delete_response.status_code == 204
    assert list_response.json() == []


def test_complete_todo_not_found() -> None:
    response = client.patch("/todos/999/complete")

    assert response.status_code == 404
    assert response.json() == {"detail": "Todo not found"}
