import pytest
from sqlalchemy import select

from backend import database
from backend.main import TodoItem


def save_todos(todos):
    with database.SessionLocal.begin() as db:
        db.add_all(database.Todo(**todo.model_dump()) for todo in todos)


def load_todos():
    with database.SessionLocal() as db:
        return [TodoItem.model_validate(todo) for todo in db.scalars(select(database.Todo))]


@pytest.fixture
def client(api_client):
    return api_client


PERIOD = {"start_at": "2026-10-13T09:00", "end_at": "2026-10-13T18:00"}  # 시작/종료 일시는 필수

def test_get_todos_empty(client):
    response = client.get("/todos")
    assert response.status_code == 200
    assert response.json() == []

def test_get_todos_with_items(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])  # save_todos 는 TodoItem 객체 리스트를 받음
    response = client.get("/todos")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Test"

def test_create_todo(client):
    todo = {"title": "Test", "description": "Test description", "status": "planned", **PERIOD}  # id 는 보내지 않음
    response = client.post("/todos", json=todo)
    assert response.status_code == 201           # 생성 성공 = 201 Created
    assert response.json()["title"] == "Test"
    assert response.json()["id"] == 1            # id 는 서버가 부여
    assert len(load_todos()) == 1                # DB에도 저장됐는지 확인

def test_create_todo_invalid(client):
    todo = {"description": "Test description", **PERIOD}   # 필수 필드 title 누락
    response = client.post("/todos", json=todo)
    assert response.status_code == 422

@pytest.mark.parametrize("missing", ["start_at", "end_at"])
def test_create_todo_without_period_returns_422(missing, client):
    todo = {"title": "Test", **PERIOD}
    del todo[missing]                            # 필수 필드 시작/종료 일시 누락
    response = client.post("/todos", json=todo)
    assert response.status_code == 422
    assert load_todos() == []

def test_create_todo_end_before_start_returns_422(client):
    todo = {"title": "Test", "start_at": "2026-10-13T18:00", "end_at": "2026-10-13T09:00"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422

def test_create_todo_date_only_end_on_start_day(client):
    # 날짜만 있는 종료 일시는 그날의 끝으로 보므로 같은 날 시작 시각보다 앞서지 않음
    todo = {"title": "Test", "start_at": "2026-10-13T18:00", "end_at": "2026-10-13"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 201

def test_create_todo_invalid_datetime_format_returns_422(client):
    todo = {"title": "Test", "start_at": "내일", "end_at": "2026-10-13T18:00"}
    response = client.post("/todos", json=todo)
    assert response.status_code == 422

@pytest.mark.parametrize("field", ["start_at", "end_at"])
@pytest.mark.parametrize("method", ["post", "put"])
def test_null_period_returns_422(client, field, method):
    payload = {"title": "Test", **PERIOD, field: None}
    url = "/todos" if method == "post" else "/todos/1"
    response = getattr(client, method)(url, json=payload)
    assert response.status_code == 422
    assert load_todos() == []


@pytest.mark.parametrize("missing", ["start_at", "end_at"])
def test_update_todo_without_period_returns_422(client, missing):
    payload = {"title": "Test", **PERIOD}
    del payload[missing]
    response = client.put("/todos/1", json=payload)
    assert response.status_code == 422
    assert load_todos() == []

def test_update_todo(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])
    updated_todo = {"title": "Updated", "description": "Updated description", "status": "done", **PERIOD}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "Updated"

def test_update_todo_not_found(client):
    updated_todo = {"title": "Updated", "description": "Updated description", "status": "done", **PERIOD}
    response = client.put("/todos/1", json=updated_todo)
    assert response.status_code == 404

def test_update_todo_status(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])

    response = client.patch("/todos/1/status", json={"status": "in_progress"})

    assert response.status_code == 200
    assert response.json() == {
        **todo.model_dump(),
        "status": "in_progress",
    }
    assert load_todos()[0].status == "in_progress"

def test_update_todo_status_not_found(client):
    response = client.patch("/todos/1/status", json={"status": "done"})

    assert response.status_code == 404
    assert response.json()["detail"] == "To-Do item not found"

def test_update_todo_status_invalid(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])

    response = client.patch("/todos/1/status", json={"status": "blocked"})

    assert response.status_code == 422
    assert load_todos()[0].status == "planned"

def test_delete_todo(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])
    response = client.delete("/todos/1")
    assert response.status_code == 204           # 삭제 성공 = 204 No Content (응답 본문 없음)
    assert load_todos() == []

def test_delete_todo_not_found(client):
    response = client.delete("/todos/1")
    assert response.status_code == 404
