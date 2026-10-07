def test_create_todo(client, todo_factory):
    todo = todo_factory("배포 생성 테스트")
    assert todo["title"] == "배포 생성 테스트"
    assert todo["id"]


def test_get_todos(client, todo_factory):
    todo = todo_factory("배포 조회 테스트")

    response = client.get("/todos")
    assert response.status_code == 200
    assert any(item["id"] == todo["id"] for item in response.json())


def test_update_todo(client, todo_factory):
    todo = todo_factory("배포 수정 전")
    updated_todo = {"title": "배포 수정 후", "description": "수정된 설명", "status": "done"}

    response = client.put(f"/todos/{todo['id']}", json=updated_todo)
    assert response.status_code == 200
    assert response.json()["title"] == "배포 수정 후"
    assert response.json()["status"] == "done"


def test_delete_todo(client, todo_factory):
    todo = todo_factory("배포 삭제 테스트")

    response = client.delete(f"/todos/{todo['id']}")
    assert response.status_code == 204

    get_response = client.get("/todos")
    assert all(item["id"] != todo["id"] for item in get_response.json())


def test_create_todo_without_title_returns_422(client):
    todo = {"description": "title 없는 항목"}  # 필수 필드 title 누락
    response = client.post("/todos", json=todo)
    assert response.status_code == 422


def test_delete_todo_not_found_returns_404(client):
    response = client.delete("/todos/999999")
    assert response.status_code == 404
