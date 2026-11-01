from datetime import datetime

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


def test_period_is_stored_as_datetime(client):
    response = client.post("/todos", json={"title": "Test", "start_at": "2026-10-13", "end_at": "2026-10-14"})
    assert response.status_code == 201
    # 날짜만 보낸 값은 시작은 0시, 종료는 그날의 끝으로 저장된다
    assert response.json()["start_at"] == "2026-10-13T00:00"
    assert response.json()["end_at"] == "2026-10-14T23:59:59"
    with database.SessionLocal() as db:
        todo = db.get(database.Todo, response.json()["id"])
        assert todo.start_at == datetime(2026, 10, 13, 0, 0)
        assert todo.end_at == datetime(2026, 10, 14, 23, 59, 59)


def test_response_keeps_minute_format(client):
    response = client.post("/todos", json={"title": "Test", **PERIOD})
    assert response.json()["start_at"] == PERIOD["start_at"]
    assert response.json()["end_at"] == PERIOD["end_at"]


def test_get_todos_sorted_by_period_in_database(client):
    for title, start in [("늦게", "2026-10-13T09:00"), ("일찍", "2026-10-12T23:00")]:
        client.post("/todos", json={"title": title, "start_at": start, "end_at": "2026-10-14T00:00"})
    with database.SessionLocal() as db:
        titles = db.scalars(select(database.Todo.title).order_by(database.Todo.start_at)).all()
    assert titles == ["일찍", "늦게"]


@pytest.mark.parametrize("value", [1760346000, "2026-10-13T09:00+09:00", "2026-10-13 09:00", "2026-10-13T09:00:00.5"])
def test_unsupported_datetime_types_return_422(client, value):
    response = client.post("/todos", json={"title": "Test", "start_at": value, "end_at": "2026-10-14T00:00"})
    assert response.status_code == 422


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


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("field", ["start_at", "end_at"])
@pytest.mark.parametrize(
    "invalid_datetime",
    ["2026-02-30", "2026-13-01", "2026-10-13T25:00", "2026-10-13T12:60"],
)
def test_todo_invalid_calendar_datetime_returns_422(client, method, field, invalid_datetime):
    original = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    if method == "put":
        save_todos([original])

    payload = {
        "title": "Test",
        "start_at": invalid_datetime if field == "start_at" else "2026-01-01T00:00",
        "end_at": "2028-03-01T00:00" if field == "start_at" else invalid_datetime,
    }
    url = "/todos" if method == "post" else "/todos/1"

    response = getattr(client, method)(url, json=payload)

    assert response.status_code == 422
    assert any(
        "유효한 날짜와 시각을 입력해야 합니다." in error["msg"]
        for error in response.json()["detail"]
    )
    assert load_todos() == ([] if method == "post" else [original])


@pytest.mark.parametrize("method", ["post", "put"])
@pytest.mark.parametrize("field", ["start_at", "end_at"])
@pytest.mark.parametrize(
    "valid_datetime",
    ["2026-02-28", "2028-02-29", "2026-10-13T23:59:59"],
)
def test_todo_valid_calendar_datetime_is_accepted(client, method, field, valid_datetime):
    if method == "put":
        save_todos([
            TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
        ])

    payload = {
        "title": "Test",
        "start_at": "2026-01-01T00:00" if field == "end_at" else valid_datetime,
        "end_at": valid_datetime if field == "end_at" else "2028-03-01T00:00",
    }
    url = "/todos" if method == "post" else "/todos/1"

    response = getattr(client, method)(url, json=payload)

    assert response.status_code == (201 if method == "post" else 200)


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

def test_delete_todo(client):
    todo = TodoItem(id=1, title="Test", description="Test description", status="planned", **PERIOD)
    save_todos([todo])
    response = client.delete("/todos/1")
    assert response.status_code == 204           # 삭제 성공 = 204 No Content (응답 본문 없음)
    assert load_todos() == []

def test_delete_todo_not_found(client):
    response = client.delete("/todos/1")
    assert response.status_code == 404


def saved_todo():
    todo = TodoItem(id=1, title="Test", description="원래 설명", status="planned", tag="work", **PERIOD)
    save_todos([todo])
    return todo


def test_patch_todo_updates_only_sent_fields(client):
    original = saved_todo()
    response = client.patch("/todos/1", json={"status": "done"})
    assert response.status_code == 200
    assert response.json() == {**original.model_dump(mode="json"), "status": "done"}
    assert load_todos() == [original.model_copy(update={"status": "done"})]


def test_patch_todo_empty_body_changes_nothing(client):
    original = saved_todo()
    response = client.patch("/todos/1", json={})
    assert response.status_code == 200
    assert load_todos() == [original]


def test_patch_todo_can_clear_tag(client):
    saved_todo()
    response = client.patch("/todos/1", json={"tag": None})
    assert response.status_code == 200
    assert response.json()["tag"] is None


@pytest.mark.parametrize("field", ["title", "start_at", "end_at", "status", "priority", "description"])
def test_patch_todo_rejects_null(client, field):
    original = saved_todo()
    response = client.patch("/todos/1", json={field: None})
    assert response.status_code == 422
    assert load_todos() == [original]


@pytest.mark.parametrize("payload", [
    {"status": "archived"},
    {"title": ""},
    {"start_at": "2026-02-30"},
    {"stauts": "done"},                  # 알 수 없는 필드
])
def test_patch_todo_invalid_returns_422(client, payload):
    original = saved_todo()
    response = client.patch("/todos/1", json=payload)
    assert response.status_code == 422
    assert load_todos() == [original]


@pytest.mark.parametrize("payload", [
    {"end_at": "2026-10-13T08:00"},      # 저장된 시작(09:00)보다 앞섬
    {"start_at": "2026-10-13T19:00"},    # 저장된 종료(18:00)보다 늦음
    {"start_at": "2026-10-14T00:00", "end_at": "2026-10-13T00:00"},
])
def test_patch_todo_end_before_start_returns_422(client, payload):
    original = saved_todo()
    response = client.patch("/todos/1", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"] == "종료 일시는 시작 일시 이후여야 합니다."
    assert load_todos() == [original]


def test_patch_todo_period_checked_with_stored_value(client):
    saved_todo()
    response = client.patch("/todos/1", json={"start_at": "2026-10-12", "end_at": "2026-10-13"})
    assert response.status_code == 200
    assert response.json()["start_at"] == "2026-10-12T00:00"
    assert response.json()["end_at"] == "2026-10-13T23:59:59"


def test_patch_todo_not_found(client):
    response = client.patch("/todos/1", json={"status": "done"})
    assert response.status_code == 404
